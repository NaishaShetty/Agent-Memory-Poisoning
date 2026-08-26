"""Shared result type for Phase 3.2-C core memory metrics.

Design principle (per the 3.2-C task brief): no metric function silently converts an
undefined case to 0. Every metric returns a `MetricResult` carrying an explicit `status`
alongside `value`, so a caller (or a test) can distinguish "computed 0" from "undefined
because the denominator/precondition does not apply here." This mirrors the fixture-driven,
structural-guarantee style already used in `phase3/evaluation/contracts/boundary.py` and
`phase3/evaluation/contracts/*.schema.json` -- the same "make ambiguity explicit and
checkable" spirit, applied to metric computation instead of schema/leakage validation.

This module has NO filesystem, network, LLM, embeddings, or randomness dependency, and no
global/mutable state. It is imported by every metric module in this package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


# Status vocabulary. Every metric function returns one of these (or a metric-specific
# variant defined in its own module docstring) so a caller can branch on *why* a value is
# None rather than guessing.
STATUS_OK = "OK"
STATUS_UNDEFINED_EMPTY_GOLD = "UNDEFINED_EMPTY_GOLD"
STATUS_UNDEFINED_EMPTY_SELECTED = "UNDEFINED_EMPTY_SELECTED"
STATUS_UNDEFINED_EMPTY_RETRIEVED = "UNDEFINED_EMPTY_RETRIEVED"
STATUS_UNDEFINED_EMPTY_TASK_SET = "UNDEFINED_EMPTY_TASK_SET"
STATUS_UNDEFINED_K_NON_POSITIVE = "UNDEFINED_K_NON_POSITIVE"
STATUS_UNDEFINED_EMPTY_SEQUENCE = "UNDEFINED_EMPTY_SEQUENCE"
STATUS_NO_HIT = "NO_HIT"


@dataclass(frozen=True)
class MetricResult:
    """Uniform result envelope returned by every function in `phase3/evaluation/metrics/`.

    Attributes
    ----------
    metric_name:
        Stable identifier for the metric (e.g. "RECALL_AT_K", "STRICT_TSR"). Not a
        human-readable label -- callers/tests match on this string.
    value:
        The computed metric value, or ``None`` if the metric is undefined for the given
        inputs (see `status`). Never silently defaulted to 0 for an undefined case.
    status:
        One of the STATUS_* constants above (or a metric-specific string documented in the
        owning module), explaining what `value` means -- in particular, why it is ``None``
        when it is.
    detail:
        A mapping with enough structure to debug the computation (e.g. numerator,
        denominator, counts, the k requested vs. the length actually available). Every
        metric function populates this; it is never left empty on a defined result.
    note:
        Optional free-text explanation, used mainly for edge cases (e.g. "k=5 exceeds
        retrieved length 3; evaluated over all 3 available items").
    """

    metric_name: str
    value: Optional[float]
    status: str
    detail: Mapping[str, Any] = field(default_factory=dict)
    note: str = ""
