"""Phase 4 P1 fix -- explicit disclosure of shared LLM-provider instances
across a campaign's attacker/victim/judge roles, and a safe, additive way for
a future real campaign to supply genuinely separate instances.

WHY THIS EXISTS
--------------------------------------------------------------------------------
The audit finding this closes: `memorygraft/milestone3_4_campaign.py`,
`sleeper_memory_poisoning/campaign.py`, and `dsrm/milestone4_campaign.py`
each construct exactly ONE `LlamaServerProvider` and reuse it for the
malicious-content generator (attacker), the target agent answering from
poisoned memory (victim), and the persistence/admission gate (judge) in the
same real campaign run -- a single point of model-specific bias or failure
that could simultaneously shape the attack content, the victim's
susceptibility to it, and the judge's assessment of it, and that was never
disclosed as a limitation distinct from the project's already-disclosed "no
defense evaluation" item.

This module does not, and cannot, change what already happened: the real,
persisted campaign logs already committed to this repository
(`calibration_run_2026-09-11*.txt`, `milestone3_4_campaign_run_*.txt`, etc.)
used one shared model instance, and remain exactly what they always were --
real evidence under that real, now-disclosed condition. What this fixes,
additively:

1. `describe_role_sharing()`/`disclose_role_sharing()` make the sharing fact
   LOUD (an explicit, printed disclosure at campaign run time) instead of
   silent -- identity-based (`is`), so it is never fooled by two providers
   that happen to be `==`-equal but are genuinely different instances.
2. Each of the three real campaign scripts' `main()` now accepts optional
   `attacker_llm_provider`/`judge_llm_provider` keyword overrides (default
   `None`, meaning "reuse the shared provider" -- IDENTICAL to today's
   behavior when not supplied, so every existing invocation and every
   already-persisted log remains exactly reproducible). A future real run
   with more than one reachable model/server can now pass genuinely distinct
   provider instances for each role without any further code change.

No frozen attack implementation (`persistence_gate.py`'s `judge_persistence`,
the injectors, the gates) is modified -- every one of them already took
`provider` as a plain parameter, generic to whichever instance a caller
passes; this was always technically possible, just never disclosed or made
easy to opt into. This module is pure new orchestration/transparency code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

ROLE_ATTACKER = "attacker"
ROLE_VICTIM = "victim"
ROLE_JUDGE = "judge"

CAMPAIGN_ROLES: Tuple[str, ...] = (ROLE_ATTACKER, ROLE_VICTIM, ROLE_JUDGE)


@dataclass(frozen=True)
class RoleSharingReport:
    """Which roles, among those supplied, share the exact same provider
    OBJECT (identity, never equality) this run. `shared_groups` lists every
    group of 2+ roles backed by one instance; `all_distinct` is True only
    when every supplied role has its own, separate instance."""

    role_provider_ids: Mapping[str, int]  # role -> id(provider), for audit/logging
    shared_groups: Tuple[Tuple[str, ...], ...]
    all_distinct: bool


def describe_role_sharing(**role_providers: object) -> RoleSharingReport:
    """`role_providers` is role_name=provider_instance kwargs for any subset
    of `CAMPAIGN_ROLES` (unknown role names are rejected -- a typo here must
    not silently produce an empty, falsely-reassuring report)."""
    unknown = set(role_providers) - set(CAMPAIGN_ROLES)
    if unknown:
        raise ValueError(f"Unknown campaign role(s): {sorted(unknown)!r}; expected a subset of {CAMPAIGN_ROLES!r}.")
    if len(role_providers) < 2:
        raise ValueError("describe_role_sharing needs at least 2 roles to compare.")

    by_identity: Dict[int, list] = {}
    for role, provider in role_providers.items():
        by_identity.setdefault(id(provider), []).append(role)

    role_provider_ids = {role: id(provider) for role, provider in role_providers.items()}
    shared_groups = tuple(
        tuple(sorted(roles)) for roles in by_identity.values() if len(roles) > 1
    )
    return RoleSharingReport(
        role_provider_ids=role_provider_ids,
        shared_groups=shared_groups,
        all_distinct=len(shared_groups) == 0,
    )


def disclose_role_sharing(campaign_label: str, **role_providers: object) -> RoleSharingReport:
    """Print an explicit disclosure line for every group of roles sharing one
    provider instance this run, then return the same report for the caller
    to persist/log alongside the campaign's other real evidence. Prints
    nothing extra (beyond one confirming line) when every role already has
    its own distinct instance -- the disclosure is proportionate to what is
    actually true this run, never boilerplate noise."""
    report = describe_role_sharing(**role_providers)
    if report.all_distinct:
        print(f"[{campaign_label}] role-provider disclosure: all {len(role_providers)} roles use distinct model instances this run.")
        return report
    for group in report.shared_groups:
        print(
            f"[{campaign_label}] DISCLOSURE: roles {list(group)} share ONE model instance "
            "this run -- a single point of model-specific bias/failure across those roles "
            "(see phase4/shared/role_provider_disclosure.py module docstring). Not a defect "
            "in this run's own real evidence, but a confound this project's earlier campaigns "
            "did not previously disclose separately from the 'no defense evaluation' limitation."
        )
    return report


__all__ = [
    "ROLE_ATTACKER",
    "ROLE_VICTIM",
    "ROLE_JUDGE",
    "CAMPAIGN_ROLES",
    "RoleSharingReport",
    "describe_role_sharing",
    "disclose_role_sharing",
]
