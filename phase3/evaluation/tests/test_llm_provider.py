"""Phase 3.3-B tests for `phase3.evaluation.llm.provider`.

Test kinds, per the mission's explicit instruction to distinguish them and never report
a mock result as a real-runtime result:

- UNIT_TEST: mocked transport (`TransportFn` injection, no network, no process). Runs in
  every regression pass unconditionally.
- REAL_RUNTIME_TEST: actually opens a socket to a real `llama-server.exe` and gets a real
  Qwen3-8B response. Only runs if a server happens to be reachable at
  `http://127.0.0.1:8811` when the test executes; otherwise `pytest.skip()`s with an
  explicit reason (same pattern `test_foundation_conformance_h4.py` already uses for
  "real library not importable in this interpreter"). NEVER silently downgrades to a
  mock and reports success -- if the server is unreachable, the test is SKIPPED, not
  passed.
"""

from __future__ import annotations

import json

import pytest

from phase3.evaluation.llm.provider import (
    GenerationConfig,
    LlamaServerEndpoint,
    LlamaServerProvider,
    LLMProviderConfigurationMismatchError,
    LLMProviderConnectionError,
    LLMProviderUnexpectedResponseError,
    ModelIdentity,
    QWEN3_8B_Q4_K_M_IDENTITY,
    _RawHttpResponse,
    clean_baseline_generation_config,
)

pytestmark = pytest.mark.filterwarnings("ignore")


def _config(**overrides) -> GenerationConfig:
    base = dict(temperature=0.0, seed=42, max_tokens=32, enable_thinking=False, n_ctx=2048)
    base.update(overrides)
    return GenerationConfig(**base)


def _mock_chat_response(
    content: str = "PRIMES: 23, 29, 31\nSUM: 83",
    finish_reason: str = "stop",
    system_fingerprint: str = "b10717-a32af33de",
    status: int = 200,
) -> _RawHttpResponse:
    body = json.dumps(
        {
            "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            "system_fingerprint": system_fingerprint,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    return _RawHttpResponse(status=status, body=body)


class TestGenerationConfigExplicitness:
    """UNIT_TEST -- enable_thinking must never have an implicit default (Part 5/Part 33
    of PHASE3_3_EXPERIMENTAL_SPEC.md; the CRITICAL instruction in the 3.3-B mission)."""

    def test_generation_config_requires_explicit_enable_thinking_bool(self):
        with pytest.raises(TypeError):
            GenerationConfig(temperature=0.0, seed=1, max_tokens=10, n_ctx=1024)  # type: ignore[call-arg]

    def test_generation_config_rejects_non_bool_enable_thinking(self):
        with pytest.raises(ValueError):
            GenerationConfig(
                temperature=0.0, seed=1, max_tokens=10, enable_thinking="false", n_ctx=1024  # type: ignore[arg-type]
            )

    def test_clean_baseline_config_defaults_enable_thinking_false_and_n_ctx_4096(self):
        cfg = clean_baseline_generation_config()
        assert cfg.enable_thinking is False
        assert cfg.n_ctx == 4096  # NOT 16384 -- see Context Policy, B.0 VRAM headroom


class TestGenerateUnit:
    """UNIT_TEST -- mocked transport, no network."""

    def test_generate_returns_parsed_result_on_success(self):
        provider = LlamaServerProvider(
            LlamaServerEndpoint(),
            post_json=lambda url, body, timeout: _mock_chat_response(),
        )
        result = provider.generate([{"role": "user", "content": "hi"}], _config())
        assert result.text == "PRIMES: 23, 29, 31\nSUM: 83"
        assert result.finish_reason == "stop"
        assert result.prompt_tokens == 12
        assert result.completion_tokens == 8
        assert result.server_fingerprint == "b10717-a32af33de"

    def test_generate_sends_enable_thinking_in_chat_template_kwargs(self):
        captured = {}

        def fake_post(url, body, timeout):
            captured["payload"] = json.loads(body.decode("utf-8"))
            return _mock_chat_response()

        provider = LlamaServerProvider(LlamaServerEndpoint(), post_json=fake_post)
        provider.generate([{"role": "user", "content": "hi"}], _config(enable_thinking=True))
        assert captured["payload"]["chat_template_kwargs"] == {"enable_thinking": True}

    def test_generate_raises_on_non_200_status(self):
        provider = LlamaServerProvider(
            LlamaServerEndpoint(),
            post_json=lambda url, body, timeout: _RawHttpResponse(status=500, body=b'{"error":"oops"}'),
        )
        with pytest.raises(LLMProviderUnexpectedResponseError):
            provider.generate([{"role": "user", "content": "hi"}], _config())

    def test_generate_raises_on_malformed_json(self):
        provider = LlamaServerProvider(
            LlamaServerEndpoint(),
            post_json=lambda url, body, timeout: _RawHttpResponse(status=200, body=b"not json"),
        )
        with pytest.raises(LLMProviderUnexpectedResponseError):
            provider.generate([{"role": "user", "content": "hi"}], _config())

    def test_generate_raises_on_missing_choices_key(self):
        provider = LlamaServerProvider(
            LlamaServerEndpoint(),
            post_json=lambda url, body, timeout: _RawHttpResponse(
                status=200, body=json.dumps({"usage": {}}).encode("utf-8")
            ),
        )
        with pytest.raises(LLMProviderUnexpectedResponseError):
            provider.generate([{"role": "user", "content": "hi"}], _config())

    def test_generate_never_retries_internally(self):
        """No retry parameter exists on generate() at all -- a single failing transport
        call must raise exactly once, never loop."""
        call_count = {"n": 0}

        def fake_post(url, body, timeout):
            call_count["n"] += 1
            return _RawHttpResponse(status=500, body=b"{}")

        provider = LlamaServerProvider(LlamaServerEndpoint(), post_json=fake_post)
        with pytest.raises(LLMProviderUnexpectedResponseError):
            provider.generate([{"role": "user", "content": "hi"}], _config())
        assert call_count["n"] == 1

    def test_generate_round_trips_non_ascii_prompt_via_mock(self):
        """Regression coverage for the UTF-8 shell-quoting bug class documented in
        PHASE3_3_B0_LLM_FEASIBILITY.md's Chinese Sanity Check section -- runs on every
        regression pass, not only when a real server happens to be reachable."""
        captured = {}

        def fake_post(url, body, timeout):
            # The critical assertion: `body` must be valid UTF-8 bytes that decode back
            # to the exact original non-ASCII text, with no mangling.
            decoded = json.loads(body.decode("utf-8"))
            captured["decoded_content"] = decoded["messages"][0]["content"]
            return _mock_chat_response(content="北京是中华人民共和国的首都。")

        provider = LlamaServerProvider(LlamaServerEndpoint(), post_json=fake_post)
        zh_prompt = "请用一句话介绍北京。"
        result = provider.generate([{"role": "user", "content": zh_prompt}], _config())
        assert captured["decoded_content"] == zh_prompt
        assert result.text == "北京是中华人民共和国的首都。"


class TestHealthCheckAndIdentityVerification:
    """UNIT_TEST -- mocked transport."""

    def test_health_check_true_on_200(self):
        provider = LlamaServerProvider(
            LlamaServerEndpoint(), get=lambda url, timeout: _RawHttpResponse(status=200, body=b"ok")
        )
        assert provider.health_check() is True

    def test_health_check_false_on_connection_error(self):
        def raising_get(url, timeout):
            raise LLMProviderConnectionError("refused")

        provider = LlamaServerProvider(LlamaServerEndpoint(), get=raising_get)
        assert provider.health_check() is False

    def test_verify_server_identity_succeeds_on_matching_fingerprint(self):
        provider = LlamaServerProvider(
            LlamaServerEndpoint(
                expected_llama_cpp_build="b10717", expected_llama_cpp_commit="a32af33de"
            ),
            post_json=lambda url, body, timeout: _mock_chat_response(
                system_fingerprint="b10717-a32af33de"
            ),
        )
        result = provider.verify_server_identity()
        assert "b10717-a32af33de" in result["system_fingerprint"]

    def test_verify_server_identity_raises_on_mismatched_fingerprint(self):
        """This is the check that prevents silently running an experiment against the
        wrong model/build -- must raise, never warn-and-continue."""
        provider = LlamaServerProvider(
            LlamaServerEndpoint(
                expected_llama_cpp_build="b10717", expected_llama_cpp_commit="a32af33de"
            ),
            post_json=lambda url, body, timeout: _mock_chat_response(
                system_fingerprint="b99999-deadbeef"
            ),
        )
        with pytest.raises(LLMProviderConfigurationMismatchError):
            provider.verify_server_identity()


class TestModelMetadataAndFingerprint:
    """UNIT_TEST."""

    def test_model_metadata_exposes_no_backend_detail(self):
        provider = LlamaServerProvider(LlamaServerEndpoint())
        metadata = provider.model_metadata()
        # Structural check: no key here should be HTTP/process/CUDA/DLL-shaped.
        forbidden_substrings = ("url", "endpoint", "port", "process", "cuda", "dll", "pid")
        for key in metadata:
            lowered = key.lower()
            assert not any(s in lowered for s in forbidden_substrings), key
        assert metadata["repo_id"] == QWEN3_8B_Q4_K_M_IDENTITY.repo_id
        assert metadata["file_sha256"] == QWEN3_8B_Q4_K_M_IDENTITY.file_sha256

    def test_configuration_fingerprint_is_deterministic_and_config_sensitive(self):
        provider = LlamaServerProvider(LlamaServerEndpoint())
        fp1 = provider.configuration_fingerprint(_config(seed=1))
        fp2 = provider.configuration_fingerprint(_config(seed=1))
        fp3 = provider.configuration_fingerprint(_config(seed=2))
        assert fp1 == fp2
        assert fp1 != fp3

    def test_configuration_fingerprint_sensitive_to_enable_thinking(self):
        """The thinking-mode flag materially changes output shape (per B.0's finding) --
        it must change the fingerprint too, so two runs that differ only in this field
        are never mistaken for identical configurations."""
        provider = LlamaServerProvider(LlamaServerEndpoint())
        fp_off = provider.configuration_fingerprint(_config(enable_thinking=False))
        fp_on = provider.configuration_fingerprint(_config(enable_thinking=True))
        assert fp_off != fp_on


class TestRealRuntime:
    """REAL_RUNTIME_TEST -- talks to an actual llama-server process if one is reachable.

    Start a server matching PHASE3_3_B0_LLM_FEASIBILITY.md's configuration before running
    this test to exercise it for real, e.g.:

        C:\\Users\\naish\\mambench_llm_feasibility\\llama_cpp_binary\\bin\\llama-server.exe
            -m C:\\Users\\naish\\mambench_llm_feasibility\\models\\Qwen3-8B-Q4_K_M.gguf
            -ngl 99 -c 4096 --port 8811

    If no server is reachable, this test SKIPS (with an explicit reason), it does not
    fail the regression suite and does not fall back to a mock and claim success.
    """

    def _live_provider(self) -> LlamaServerProvider:
        return LlamaServerProvider(LlamaServerEndpoint(base_url="http://127.0.0.1:8811"))

    def test_generate_against_real_server_produces_coherent_answer(self):
        provider = self._live_provider()
        if not provider.health_check(timeout_sec=2.0):
            pytest.skip("No llama-server reachable at http://127.0.0.1:8811 -- REAL_RUNTIME_TEST skipped.")
        result = provider.generate(
            [{"role": "user", "content": "Reply with only the single word: OK"}],
            _config(max_tokens=10),
        )
        assert "OK" in result.text.upper()
        assert result.latency_sec > 0

    def test_generate_against_real_server_handles_chinese_prompt(self):
        provider = self._live_provider()
        if not provider.health_check(timeout_sec=2.0):
            pytest.skip("No llama-server reachable at http://127.0.0.1:8811 -- REAL_RUNTIME_TEST skipped.")
        result = provider.generate(
            [{"role": "user", "content": "请用一句话介绍北京。"}],
            _config(max_tokens=60),
        )
        assert len(result.text.strip()) > 0
        # At least one CJK character present -- a coarse, structural sanity check, not a
        # semantic/benchmark claim (per B.0's explicit "runtime sanity check only" framing).
        assert any("\u4e00" <= ch <= "\u9fff" for ch in result.text)

    def test_verify_server_identity_against_real_server(self):
        provider = self._live_provider()
        if not provider.health_check(timeout_sec=2.0):
            pytest.skip("No llama-server reachable at http://127.0.0.1:8811 -- REAL_RUNTIME_TEST skipped.")
        result = provider.verify_server_identity()
        assert QWEN3_8B_Q4_K_M_IDENTITY.llama_cpp_build in result["system_fingerprint"]
