"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- configuration/state
fingerprinting for foundation adapters.

Reuses `phase3.evaluation.security.reproducibility.fingerprint` / `canonical_serialize` /
`safe_environment_metadata` VERBATIM -- this module builds no parallel hashing system. Its
only job is to (a) define the shape of a "foundation configuration" dict worth
fingerprinting, (b) forbid secret/key/token-shaped fields from ever entering that shape,
and (c) provide a thin `fingerprint_state` wrapper for a foundation's `export_state()`
result.

Pure functions: no filesystem/network/LLM/embeddings access, no randomness.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence, Tuple

from phase3.evaluation.security.reproducibility import (
    canonical_serialize,
    fingerprint,
    safe_environment_metadata,
)

# ---------------------------------------------------------------------------
# Secret rejection
# ---------------------------------------------------------------------------

# Key-name fragments (case-insensitive substring match) that mark a field as
# secret/credential-shaped. Deliberately broad and substring-based (mirrors
# `security/leakage.py`'s conservative, name-based-not-content-based philosophy) so a
# renamed variant (e.g. "openai_api_key", "embedding_api_token") is still caught.
_SECRET_KEY_FRAGMENTS: Tuple[str, ...] = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "credential",
    "auth_header",
    "bearer",
    "private_key",
)


class ConfigurationSecretError(ValueError):
    """Raised when a foundation-configuration payload carries a secret/key/token-shaped
    field -- this is never silently stripped and fingerprinted anyway; the caller must
    remove the offending field and resubmit, so a secret can never end up baked into a
    manifest even indirectly via its fingerprint's preimage.
    """


def _find_secret_keys(payload: Any, path: str = "$") -> list:
    hits: list = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            key_str = str(key).lower()
            child_path = f"{path}.{key}"
            if any(fragment in key_str for fragment in _SECRET_KEY_FRAGMENTS):
                hits.append(child_path)
            hits.extend(_find_secret_keys(value, child_path))
    elif isinstance(payload, (list, tuple)):
        for index, item in enumerate(payload):
            hits.extend(_find_secret_keys(item, f"{path}[{index}]"))
    return hits


def reject_secrets(configuration: Mapping[str, Any]) -> Mapping[str, Any]:
    """Raise `ConfigurationSecretError` if `configuration` carries any secret/key/token-
    shaped field at any nesting depth; otherwise return it unchanged.
    """
    hits = _find_secret_keys(configuration)
    if hits:
        raise ConfigurationSecretError(
            "Foundation configuration carries secret/credential-shaped field(s), never "
            "permitted in a fingerprinted configuration view: " + ", ".join(sorted(hits))
        )
    return configuration


# ---------------------------------------------------------------------------
# Foundation configuration fingerprint
# ---------------------------------------------------------------------------


def build_foundation_configuration(
    foundation_id: str,
    foundation_version: str,
    adapter_version: str,
    configuration_parameters: Mapping[str, Any],
    storage_backend: str,
    retrieval_parameters: Mapping[str, Any],
    embedding_configuration_id: str,
    llm_configuration_id: str,
    normalization_version: str,
) -> dict:
    """Assemble a foundation-configuration dict worth fingerprinting.

    `embedding_configuration_id`/`llm_configuration_id` are IDENTIFIERS only (e.g.
    `"text-embedding-3-small"`, `"gpt-4o-mini"`) -- never the actual API key/secret used
    to reach that model. `configuration_parameters`/`retrieval_parameters` are checked via
    `reject_secrets` before assembly; the whole assembled dict is checked again, so a
    secret nested anywhere (even outside those two sub-mappings, e.g. hypothetically
    smuggled into `storage_backend` as a connection string) is still caught.
    """
    reject_secrets(configuration_parameters)
    reject_secrets(retrieval_parameters)

    config = {
        "foundation_id": foundation_id,
        "foundation_version": foundation_version,
        "adapter_version": adapter_version,
        "configuration_parameters": dict(configuration_parameters),
        "storage_backend": storage_backend,
        "retrieval_parameters": dict(retrieval_parameters),
        "embedding_configuration_id": embedding_configuration_id,
        "llm_configuration_id": llm_configuration_id,
        "normalization_version": normalization_version,
        "safe_environment_metadata": dict(safe_environment_metadata()),
    }
    reject_secrets(config)
    return config


def fingerprint_configuration(configuration: Mapping[str, Any]) -> str:
    """SHA-256 fingerprint (via `security.reproducibility.fingerprint`, reused verbatim) of
    a foundation-configuration dict, after re-checking it carries no secret.
    """
    reject_secrets(configuration)
    return fingerprint(configuration)


# ---------------------------------------------------------------------------
# Foundation state fingerprint
# ---------------------------------------------------------------------------


def fingerprint_state(state_snapshot: Any) -> str:
    """SHA-256 fingerprint (via `security.reproducibility.fingerprint`, reused verbatim) of
    a foundation's `export_state()` result. Deliberately does NOT reorder any list/
    sequence inside `state_snapshot` -- `fingerprint`'s underlying `canonical_serialize`
    already preserves list order (see that module's docstring); this wrapper adds no
    additional normalization of its own.
    """
    return fingerprint(state_snapshot)


__all__ = [
    "ConfigurationSecretError",
    "reject_secrets",
    "build_foundation_configuration",
    "fingerprint_configuration",
    "fingerprint_state",
    "canonical_serialize",
]
