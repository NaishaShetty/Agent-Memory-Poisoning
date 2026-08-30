"""Shared, deterministic scaffolding for the four Mock* foundation adapters.

Pure, in-memory, deterministic: a monotonically-incrementing internal counter stands in
for a timestamp (never `datetime.now()`/`time.time()`, which would make two otherwise-
identical mock runs produce different trace timestamps and undermine the "MOCK_CONFORMANCE
is deterministic" guarantee this package tests for) and for auto-assigned ids (never
`uuid4()`/`random`, for the same reason).
"""

from __future__ import annotations

from typing import Any, Mapping

from phase3.evaluation.foundations.adapter import (
    FOUNDATION_AVAILABLE,
    FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE,
    FoundationField,
    FoundationIdentity,
)
from phase3.evaluation.foundations.fingerprinting import reject_secrets
from phase3.evaluation.foundations.registry import PREPARED_CANDIDATE
from phase3.evaluation.foundations.security import enforce_foundation_call_boundary


class DeterministicClock:
    """A monotonically-incrementing counter standing in for wall-clock time, formatted as
    a sortable string. Never wraps `time.time()`/`datetime.now()`."""

    def __init__(self) -> None:
        self._counter = 0

    def tick(self) -> str:
        self._counter += 1
        return f"T{self._counter:06d}"


def check_call_payload(content: Mapping[str, Any], metadata: Mapping[str, Any] | None) -> None:
    """Every mock adapter's `add_memory`/`update_memory` call runs its `content`/
    `metadata` arguments through the evaluator/agent security boundary (Step 7's leakage-
    injection test target) and through secret-rejection (a `metadata` payload is exactly
    the kind of place a caller might accidentally stash a credential).
    """
    enforce_foundation_call_boundary(dict(content))
    if metadata is not None:
        enforce_foundation_call_boundary(dict(metadata))
        reject_secrets(metadata)


def not_supported(operation: str, reason: str) -> FoundationField:
    return FoundationField(
        value=None,
        availability=FOUNDATION_NOT_SUPPORTED_BY_ARCHITECTURE,
        operation=operation,
        note=reason,
    )


def available(operation: str, value: Any, note: str = "") -> FoundationField:
    return FoundationField(value=value, availability=FOUNDATION_AVAILABLE, operation=operation, note=note)


def make_identity(foundation_id: str, foundation_name: str, adapter_version: str) -> FoundationIdentity:
    return FoundationIdentity(
        foundation_id=foundation_id,
        foundation_name=foundation_name,
        adapter_version=adapter_version,
        status=PREPARED_CANDIDATE,
    )


__all__ = [
    "DeterministicClock",
    "check_call_payload",
    "not_supported",
    "available",
    "make_identity",
]
