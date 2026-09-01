"""Phase 3.3-B -- `LLMProvider` abstraction + `LlamaServerProvider`, the concrete backend
talking to an official llama.cpp `llama-server.exe` process over its OpenAI-compatible
HTTP API.

WHY THIS BACKEND, NOT `llama_cpp.Llama(...)`
--------------------------------------------------------------------------------
`PHASE3_3_B0_LLM_FEASIBILITY.md`'s Backend Decision section documents, with reproduced
evidence, that the pip `llama-cpp-python` CUDA wheel crashes unconditionally on this
machine's CPU with `STATUS_ILLEGAL_INSTRUCTION` (a CPU-dispatch defect in that specific
wheel, not in llama.cpp or in Qwen3-8B). The official `ggml-org/llama.cpp` GitHub release
binary (build b10717, `win-cuda-12.4-x64`) does not have this defect and is the confirmed
working path. This module therefore NEVER imports `llama_cpp` -- it only ever speaks
plain HTTP (stdlib `urllib`, zero third-party dependency) to a `llama-server.exe` process
that the caller is responsible for starting/stopping. This also means this module places
no constraint on which Python environment it is imported from (unlike `mem0ai`, which is
only importable inside the isolated `C:\\h4venv` per `foundations_real/environment.py`) --
it works identically in the main repo test environment and in `C:\\h4venv`.

WHAT STAYS HIDDEN BEHIND THE PROVIDER BOUNDARY (Part 4 of PHASE3_3_EXPERIMENTAL_SPEC.md)
--------------------------------------------------------------------------------
`LLMProvider.generate/model_metadata/configuration_fingerprint` is the entire surface an
agent or evaluator ever sees. The HTTP endpoint, the request/response JSON shape, the
`chat_template_kwargs.enable_thinking` mechanism Qwen3 specifically requires (see
B.0's Reproducibility section -- Qwen3 defaults to a thinking mode that can silently
consume an entire generation budget with no final answer unless this is set explicitly),
and the llama-server-specific `system_fingerprint` response field are all internal to
this module. `ModelIdentity`/`GenerationResult` are the only shapes exposed outward, and
neither carries any backend-specific detail (no URL, no process handle, no DLL path).

NO SILENT RETRIES
--------------------------------------------------------------------------------
`LlamaServerProvider.generate()` makes exactly one HTTP request and never retries
internally. A caller that wants retry behavior (the agent runtime, per
`agent_runtime/runner.py`) must call `generate()` again itself and record every attempt
in the trace -- this module deliberately has no retry parameter, so "retried silently"
is not a possible failure mode of this class.

UTF-8 SAFETY
--------------------------------------------------------------------------------
`PHASE3_3_B0_LLM_FEASIBILITY.md`'s Chinese Sanity Check section documents a real bug
class: passing a non-ASCII prompt through inline shell-interpolated `curl -d` arguments
silently mangled the text and produced an incoherent response, root-caused to shell/
encoding, not the model. This module never touches a shell: the JSON request body is
built with `json.dumps(..., ensure_ascii=False)`, encoded explicitly as UTF-8 bytes
(`.encode("utf-8")`), and sent as the literal HTTP request body via `urllib.request` --
there is no shell, no argv, no intermediate text encoding step where mangling could occur.
See `phase3/evaluation/tests/test_llm_provider.py::test_generate_round_trips_non_ascii_prompt_via_mock`
for regression coverage on this exact class of bug (with a mocked transport, so it runs in
every regression pass, not only when a real server happens to be up) and
`test_generate_against_real_server_handles_chinese_prompt` for the REAL_RUNTIME_TEST that
exercises the same path against an actual running server when one is reachable.
"""

from __future__ import annotations

import abc
import dataclasses
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, List, Mapping, MutableMapping, Optional, Sequence

from phase3.evaluation.security.reproducibility import fingerprint

# ---------------------------------------------------------------------------
# Errors -- typed, never silently swallowed by this module.
# ---------------------------------------------------------------------------


class LLMProviderError(Exception):
    """Base class for every error this package raises."""


class LLMProviderConnectionError(LLMProviderError):
    """The server was unreachable (connection refused, DNS failure, etc.)."""


class LLMProviderTimeoutError(LLMProviderError):
    """The request exceeded `GenerationConfig.request_timeout_sec`."""


class LLMProviderUnexpectedResponseError(LLMProviderError):
    """The server responded, but the response was not shaped as expected (missing
    `choices`, malformed JSON, non-2xx status, etc.)."""


class LLMProviderConfigurationMismatchError(LLMProviderError):
    """The reachable server's reported identity does not match the configured expected
    model/backend identity -- raised by `verify_server_identity()` so a caller never
    silently runs an experiment against the wrong model/build."""


# ---------------------------------------------------------------------------
# Model identity -- exactly the Phase 3.3-B.0-established Qwen3-8B artifact.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelIdentity:
    """Everything `PHASE3_3_EXPERIMENTAL_SPEC.md` Part 33 requires recording about the
    model artifact and the backend build that serves it. Every field here was directly
    verified in Phase 3.3-B.0 (file SHA-256 checked against the HF repo's own Git-LFS
    pointer hash, repo revision read from `HfApi.model_info().sha`, llama.cpp build/commit
    read from `llama-cli.exe --version`) -- nothing here is guessed or assumed.
    """

    repo_id: str
    file_name: str
    repo_revision: str
    file_sha256: str
    quantization: str
    llama_cpp_build: str
    llama_cpp_commit: str


# The one and only LLM baseline established by Phase 3.3-B.0. Not a default meant to be
# silently overridden -- a caller targeting a different model/quantization must construct
# its own `ModelIdentity` explicitly (and, per the 3.3-A spec, that would be a distinct,
# separately-recorded experimental condition, not a transparent swap).
QWEN3_8B_Q4_K_M_IDENTITY = ModelIdentity(
    repo_id="Qwen/Qwen3-8B-GGUF",
    file_name="Qwen3-8B-Q4_K_M.gguf",
    repo_revision="7c41481f57cb95916b40956ab2f0b139b296d974",
    file_sha256="d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785",
    quantization="Q4_K_M",
    llama_cpp_build="b10717",
    llama_cpp_commit="a32af33de",
)


# ---------------------------------------------------------------------------
# Generation configuration -- every field the 3.3-A spec (Part 3) requires as an
# explicit, recorded controlled variable. `enable_thinking` has NO implicit default
# inherited from the backend -- it is a required-by-construction field on this
# dataclass, always explicit, per the mission's CRITICAL instruction and B.0's finding.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenerationConfig:
    temperature: float
    seed: int
    max_tokens: int
    enable_thinking: bool
    n_ctx: int
    request_timeout_sec: float = 120.0

    def __post_init__(self) -> None:
        if not isinstance(self.enable_thinking, bool):
            raise ValueError(
                "enable_thinking must be an explicit bool (True or False) -- there is no "
                "implicit default in this framework. See PHASE3_3_B0_LLM_FEASIBILITY.md's "
                "Reproducibility section for why this must never be left to the backend."
            )


# Clean-baseline default per the mission's explicit instruction ("For the initial clean
# baseline use enable_thinking = false unless an experiment explicitly studies
# thinking-mode behavior"). This is a convenience CONSTRUCTOR, not a hidden default
# threaded into `GenerationConfig` itself -- `GenerationConfig` has no default for
# `enable_thinking` at all, so a caller must always pass it, explicitly, one way or another.
def clean_baseline_generation_config(
    *,
    max_tokens: int = 512,
    n_ctx: int = 4096,
    temperature: float = 0.0,
    seed: int = 42,
    request_timeout_sec: float = 120.0,
) -> GenerationConfig:
    """`n_ctx=4096` default, NOT 16384. Per B.0, 16K context leaves only ~4.8% VRAM
    headroom for the LLM alone, before any foundation-side GPU usage is added -- per the
    mission's explicit Context Policy instruction, 3.3-B must not default to 16K merely
    because the model supports it. 4096 was the second-smallest context B.0 measured
    (5223/6141 MiB, ~85% used, leaving genuine headroom for a concurrent foundation
    process) and is a conservative, evidence-based starting point for the pilot -- the
    pilot itself (see `agent_runtime/pilot_mem0_locomo.py`) measures whether this holds
    under the actual combined Qwen+Mem0 workload before any larger context is proposed.
    """
    return GenerationConfig(
        temperature=temperature,
        seed=seed,
        max_tokens=max_tokens,
        enable_thinking=False,
        n_ctx=n_ctx,
        request_timeout_sec=request_timeout_sec,
    )


@dataclass(frozen=True)
class LlamaServerEndpoint:
    base_url: str = "http://127.0.0.1:8811"
    expected_llama_cpp_build: str = QWEN3_8B_Q4_K_M_IDENTITY.llama_cpp_build
    expected_llama_cpp_commit: str = QWEN3_8B_Q4_K_M_IDENTITY.llama_cpp_commit


@dataclass(frozen=True)
class GenerationResult:
    """The only shape `LlamaServerProvider.generate()` returns. No HTTP/process detail
    survives into this object except `server_fingerprint` (a short, already-opaque
    string llama-server itself emits, treated as data, never parsed for internals)."""

    text: str
    finish_reason: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    latency_sec: float
    server_fingerprint: Optional[str]
    raw_response: Mapping[str, Any]


# ---------------------------------------------------------------------------
# LLMProvider abstraction (Part 4 of PHASE3_3_EXPERIMENTAL_SPEC.md)
# ---------------------------------------------------------------------------


class LLMProvider(abc.ABC):
    """The complete surface an agent or evaluator may ever call. Any future provider
    (OpenAI-compatible cloud, Gemini, a different local backend) implements exactly this
    interface -- no more, no less -- so agent/evaluator code never branches on which
    concrete provider is in use."""

    @abc.abstractmethod
    def generate(
        self, messages: Sequence[Mapping[str, str]], config: GenerationConfig
    ) -> GenerationResult: ...

    @abc.abstractmethod
    def model_metadata(self) -> Mapping[str, Any]: ...

    @abc.abstractmethod
    def configuration_fingerprint(self, config: GenerationConfig) -> str: ...


# A pluggable transport hook purely for unit testing (dependency injection), never used
# in real operation -- production callers always use the default (`_http_post_json`,
# real `urllib.request`). Keeping this as an explicit constructor parameter, rather than
# monkeypatching `urllib` in tests, keeps the real HTTP path identical between tests and
# production and makes "this test used a mock transport" visible at the call site.
TransportFn = Callable[[str, bytes, float], "_RawHttpResponse"]


@dataclass(frozen=True)
class _RawHttpResponse:
    status: int
    body: bytes


def _http_post_json(url: str, body: bytes, timeout_sec: float) -> _RawHttpResponse:
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            return _RawHttpResponse(status=response.status, body=response.read())
    except urllib.error.HTTPError as exc:
        # A non-2xx response still has a readable body (often a JSON error payload from
        # llama-server) -- surface it via body/status rather than discarding it.
        return _RawHttpResponse(status=exc.code, body=exc.read())
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError) or "timed out" in str(exc.reason).lower():
            raise LLMProviderTimeoutError(str(exc)) from exc
        raise LLMProviderConnectionError(str(exc)) from exc
    except TimeoutError as exc:
        raise LLMProviderTimeoutError(str(exc)) from exc


def _http_get(url: str, timeout_sec: float) -> _RawHttpResponse:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            return _RawHttpResponse(status=response.status, body=response.read())
    except urllib.error.HTTPError as exc:
        return _RawHttpResponse(status=exc.code, body=exc.read())
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError) or "timed out" in str(exc.reason).lower():
            raise LLMProviderTimeoutError(str(exc)) from exc
        raise LLMProviderConnectionError(str(exc)) from exc
    except TimeoutError as exc:
        raise LLMProviderTimeoutError(str(exc)) from exc


class LlamaServerProvider(LLMProvider):
    """Concrete `LLMProvider` backed by a `llama-server.exe` process reachable at
    `endpoint.base_url`. Does NOT start, stop, or manage that process -- server lifecycle
    is the caller's responsibility (see module docstring and
    `agent_runtime/pilot_mem0_locomo.py` for the RESET/INGEST/RUN/EVALUATE orchestration
    that owns process lifecycle for the pilot). This class only ever assumes a server MAY
    be running; every method that needs one checks reachability explicitly and raises a
    typed error rather than assuming.
    """

    def __init__(
        self,
        endpoint: LlamaServerEndpoint,
        model_identity: ModelIdentity = QWEN3_8B_Q4_K_M_IDENTITY,
        post_json: TransportFn = None,
        get: TransportFn = None,
    ) -> None:
        self._endpoint = endpoint
        self._model_identity = model_identity
        self._post_json = post_json or (
            lambda url, body, timeout: _http_post_json(url, body, timeout)
        )
        self._get = get or (lambda url, timeout: _http_get(url, timeout))

    # -- reachability / identity verification -----------------------------------

    def health_check(self, timeout_sec: float = 5.0) -> bool:
        """Returns True iff `/health` responds with HTTP 200. Never raises for a plain
        unreachable server -- returns False -- but DOES propagate a genuine transport
        error distinct from "unreachable" (there is none to distinguish for a GET, so
        this simply returns False on any exception from `_get`)."""
        try:
            response = self._get(self._endpoint.base_url.rstrip("/") + "/health", timeout_sec)
            return response.status == 200
        except LLMProviderError:
            return False

    def verify_server_identity(self, timeout_sec: float = 10.0) -> Mapping[str, Any]:
        """Confirms the reachable server is genuinely the configured build/commit, not
        merely "some server on this port." Performs one minimal generation call (the
        cheapest reliable way to read llama-server's `system_fingerprint` field; `/v1/models`
        does not expose it) and checks the fingerprint's build/commit prefix against
        `endpoint.expected_llama_cpp_build`/`expected_llama_cpp_commit`.

        Raises
        ------
        LLMProviderConnectionError / LLMProviderTimeoutError
            If the server is not reachable at all.
        LLMProviderConfigurationMismatchError
            If the server IS reachable but its `system_fingerprint` does not match the
            expected build/commit -- this is the check that prevents a caller from
            silently running an experiment against a different model/build than intended
            (per the mission's explicit "must verify that the server corresponds to the
            expected configuration" requirement).
        """
        probe_config = GenerationConfig(
            temperature=0.0,
            seed=0,
            max_tokens=1,
            enable_thinking=False,
            n_ctx=256,
            request_timeout_sec=timeout_sec,
        )
        result = self.generate(
            [{"role": "user", "content": "ping"}], probe_config
        )
        fp = result.server_fingerprint or ""
        expected = f"{self._endpoint.expected_llama_cpp_build}-{self._endpoint.expected_llama_cpp_commit}"
        if expected not in fp:
            raise LLMProviderConfigurationMismatchError(
                f"Server system_fingerprint {fp!r} does not contain expected "
                f"{expected!r}; refusing to proceed against an unverified server."
            )
        return {"system_fingerprint": fp, "expected": expected}

    # -- LLMProvider interface ---------------------------------------------------

    def generate(
        self, messages: Sequence[Mapping[str, str]], config: GenerationConfig
    ) -> GenerationResult:
        payload: MutableMapping[str, Any] = {
            "messages": list(messages),
            "temperature": config.temperature,
            "seed": config.seed,
            "max_tokens": config.max_tokens,
            "chat_template_kwargs": {"enable_thinking": config.enable_thinking},
        }
        # ensure_ascii=False + explicit .encode("utf-8") -- see module docstring's UTF-8
        # SAFETY section. Never build this body via string interpolation or a shell.
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        url = self._endpoint.base_url.rstrip("/") + "/v1/chat/completions"

        t0 = time.time()
        response = self._post_json(url, body, config.request_timeout_sec)
        latency = time.time() - t0

        if response.status != 200:
            raise LLMProviderUnexpectedResponseError(
                f"llama-server returned HTTP {response.status}: "
                f"{response.body.decode('utf-8', errors='replace')[:500]}"
            )
        try:
            data = json.loads(response.body.decode("utf-8"))
            choice = data["choices"][0]
            message = choice["message"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderUnexpectedResponseError(
                f"llama-server response was not shaped as expected: {exc}; "
                f"raw={response.body[:500]!r}"
            ) from exc

        usage = data.get("usage") or {}
        return GenerationResult(
            text=message.get("content") or "",
            finish_reason=choice.get("finish_reason", "UNKNOWN"),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_sec=latency,
            server_fingerprint=data.get("system_fingerprint"),
            raw_response=data,
        )

    def model_metadata(self) -> Mapping[str, Any]:
        return dataclasses.asdict(self._model_identity)

    def configuration_fingerprint(self, config: GenerationConfig) -> str:
        # Reuses phase3.evaluation.security.reproducibility.fingerprint() verbatim --
        # never a bespoke hash -- per PHASE3_3_EXPERIMENTAL_SPEC.md Part 33's instruction
        # to record a configuration_fingerprint the same way every other Phase 3.2/3.3
        # fingerprint is computed.
        return fingerprint(
            {
                "model_identity": dataclasses.asdict(self._model_identity),
                "temperature": config.temperature,
                "seed": config.seed,
                "max_tokens": config.max_tokens,
                "enable_thinking": config.enable_thinking,
                "n_ctx": config.n_ctx,
            }
        )


__all__ = [
    "LLMProviderError",
    "LLMProviderConnectionError",
    "LLMProviderTimeoutError",
    "LLMProviderUnexpectedResponseError",
    "LLMProviderConfigurationMismatchError",
    "ModelIdentity",
    "QWEN3_8B_Q4_K_M_IDENTITY",
    "GenerationConfig",
    "clean_baseline_generation_config",
    "LlamaServerEndpoint",
    "GenerationResult",
    "LLMProvider",
    "LlamaServerProvider",
]
