"""Phase 6.9, Item 2 -- external corroboration: analysis, then experimental
test, per the required protocol in STAGE_6_9_QUEUE.md ("analyze consistency
with Signal Contract and Threat Model BEFORE implementation; implement only if
scientifically justified; do not assume the mechanism is safe or useful; test
experimentally").

======================================================================
ANALYSIS (required before any implementation below)
======================================================================

PROPOSED MECHANISM: for a candidate in the CURRENT retrieval pool, additionally
compare its content against a REFERENCE SET drawn from the broader memory
store, restricted to memories whose PERSISTED MGP state is TRUSTED (read via
`GovernanceLedger.current_state()`). A candidate whose apparent in-pool
"majority" finds no echo anywhere in this wider trusted reference is more
suspicious than one that does -- this directly targets the coordinated-
poisoning weakness (Stage 6.6/6.9 Item 1): a manufactured, in-pool-only
consensus should look different from a genuinely well-established fact that
also appears in independently-admitted, already-trusted content.

Signal Contract consistency (`DEFENSE_SIGNAL_CONTRACT.md`):
- The reference set's membership criterion is the candidate's own persisted
  MGP security state (TRUSTED) -- an already-sanctioned signal source (Policy
  document Section 1), never a ground-truth or evaluator-only label. CONSISTENT.
- The comparison itself is lexical/semantic content similarity -- the same
  primitive already sanctioned for retrieval consensus (Section 2.3) and
  admission signals (Section 2.1). CONSISTENT.
- No new field category is introduced; this is an additional QUERY against
  already-legitimate data (persisted state + content), not a new kind of
  signal. CONSISTENT with the contract as written.

Threat Model consistency (`DEFENSE_THREAT_MODEL.md`) -- the real risk:
- If an attacker has ALREADY gotten one or more poisoned memories marked
  TRUSTED (via evasion of Stages 6.5/6.6, or before those defenses existed),
  using the "trusted store" as a corroboration reference could AMPLIFY that
  earlier poison's influence: poison A (already TRUSTED) corroborates poison
  B, which corroborates poison C, compounding rather than containing the
  attack. This is structurally the SAME class of weakness the 6.2 literature
  audit already found in A-MemGuard (reward correlated agreement; coordinated
  content look trustworthy). CONSISTENT WITH THE THREAT MODEL ONLY IF THIS
  RISK IS TESTED, NOT ASSUMED AWAY.

CONCLUSION: the mechanism does not require any new evaluator-only signal and
is structurally consistent with the existing contract, but its central claimed
benefit (distinguishing genuine consensus from manufactured consensus) is
exactly the scenario where it could ALSO fail (if the "trusted" reference
itself already contains undetected poison). This is scientifically justified
to prototype and test experimentally -- NOT to adopt as a default -- per the
queue's own instruction. The prototype below is built accordingly: a plain
function, no wiring into any shipped guard, tested for BOTH the case where it
plausibly helps and the case where it could hurt.
======================================================================
"""

from __future__ import annotations

from typing import Dict, Sequence

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS, EvaluatorOnlyLeakageError
from phase6.defense.retrieval.signals import _jaccard_similarity, _tokenize


def external_corroboration_signal(
    candidate_content: str, trusted_reference_contents: Sequence[str]
) -> Dict[str, float]:
    """Score in [0, 1]: the candidate's maximum lexical similarity to any
    content in `trusted_reference_contents` (memories whose PERSISTED MGP
    state is TRUSTED, per the analysis above -- this function does not read
    any ledger itself; the caller supplies the reference contents). Returns
    0.0 for an empty reference set (no corroboration possible, not "fully
    corroborated" -- absence of evidence is not evidence of absence, encoded
    honestly as the floor, not the ceiling)."""
    if not trusted_reference_contents:
        score = 0.0
    else:
        candidate_tokens = _tokenize(candidate_content)
        score = max(
            _jaccard_similarity(candidate_tokens, _tokenize(ref)) for ref in trusted_reference_contents
        )
    signal = {"external_corroboration_score": score}
    offending = set(signal.keys()) & FORBIDDEN_SIGNAL_KEYS
    if offending:  # unreachable given the fixed key name, kept for parity/defense-in-depth
        raise EvaluatorOnlyLeakageError(f"external_corroboration_signal leaked {offending!r}")
    return signal


# ======================================================================
# EXPERIMENTAL TEST -- both directions, run for real, reported honestly
# ======================================================================

if __name__ == "__main__":
    # Scenario A: corroboration plausibly HELPS. The lone truth, locally
    # outvoted by a manufactured in-pool majority, DOES appear (independently
    # worded) in the wider trusted store -- e.g., an earlier, unrelated
    # session already recorded the same real fact.
    truth = "The deployment safety check actually failed and was never approved"
    poison_majority = [
        "The deployment was already validated and approved for release",
        "The deployment has been validated and approved for release",
        "This deployment was validated and already approved for release",
    ]
    trusted_reference_helps = [
        "Engineering confirmed the deployment safety check did not pass",
        "The release was blocked because the safety review failed",
    ]
    print("=== Scenario A: external corroboration plausibly helps ===")
    print("truth corroboration:", external_corroboration_signal(truth, trusted_reference_helps))
    print(
        "poison corroboration (max over majority):",
        max(
            external_corroboration_signal(p, trusted_reference_helps)["external_corroboration_score"]
            for p in poison_majority
        ),
    )

    # Scenario B: the REAL RISK. The "trusted" reference store has ALREADY
    # been poisoned by an earlier, undetected instance of the SAME lie
    # (evaded Stage 6.5/6.6 previously, or existed before Phase 6 was
    # deployed) -- does external corroboration now AMPLIFY the poison
    # instead of catching it?
    trusted_reference_already_poisoned = [
        "Deployment approval was confirmed by the release team last week",
    ]
    print()
    print("=== Scenario B: the trusted reference is ITSELF already poisoned ===")
    print(
        "poison corroboration (max over majority):",
        max(
            external_corroboration_signal(p, trusted_reference_already_poisoned)["external_corroboration_score"]
            for p in poison_majority
        ),
    )
    print("truth corroboration:", external_corroboration_signal(truth, trusted_reference_already_poisoned))
