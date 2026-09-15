"""Phase 6.18 -- summary analysis over the real failure catalog."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Tuple

from phase6.evaluation.failures.catalog import FAILURE_CATALOG, FailureCase
from phase6.evaluation.failures.taxonomy import FailureCause


@dataclass(frozen=True)
class FailureSummary:
    total_cases: int
    unresolved_cases: int
    resolved_cases: int
    primary_cause_counts: Dict[str, int]
    cases_using_proposed_extension: Tuple[str, ...]


def summarize(catalog: Tuple[FailureCase, ...] = FAILURE_CATALOG) -> FailureSummary:
    if not catalog:
        raise ValueError("summarize: catalog must be non-empty.")
    resolved = [c for c in catalog if c.is_resolved]
    unresolved = [c for c in catalog if not c.is_resolved]
    primary_counts = Counter(c.primary_cause.value for c in catalog)
    extension_cases = tuple(
        c.case_id
        for c in catalog
        if c.primary_cause == FailureCause.F15_NO_APPLICABLE_MECHANISM_PROPOSED_EXTENSION
        or FailureCause.F15_NO_APPLICABLE_MECHANISM_PROPOSED_EXTENSION in c.secondary_causes
    )
    return FailureSummary(
        total_cases=len(catalog),
        unresolved_cases=len(unresolved),
        resolved_cases=len(resolved),
        primary_cause_counts=dict(primary_counts),
        cases_using_proposed_extension=extension_cases,
    )
