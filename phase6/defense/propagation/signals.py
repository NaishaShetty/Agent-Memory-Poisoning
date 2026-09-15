"""Phase 6.7 -- Propagation & Lineage Containment: the lineage-taint signal.

RESEARCH QUESTION
--------------------------------------------------------------------------------
"Can memory poisoning be contained after the original poisoned memory has
already entered memory?" -- i.e., when M2 is DERIVED_FROM a suspicious/
quarantined/blocked M1, should M2 automatically inherit M1's suspicion?

THE ANSWER THIS MODULE IMPLEMENTS: NO, NOT AUTOMATICALLY.
--------------------------------------------------------------------------------
`docs/phase6/MEMORY_GOVERNANCE_POLICY.md` Section 8 and
`docs/phase6/DEFENSE_SCOPE_MATRIX.md` Section 2 both already committed to this
design before any code was written: a descendant's own assessment treats
"derived from a tainted ancestor" as ONE legitimate signal among several,
weighted no higher than other signals -- never an automatic transitive
relabeling. This module is where that commitment becomes a real, testable
formula.

THE FORMULA, AND WHY
--------------------------------------------------------------------------------
For a descendant memory with one or more ancestors (each carrying its own
already-persisted MGP security state and its own content), this module
computes:

    contribution(ancestor) = severity(ancestor.security_state)
                              * distance_decay(ancestor.distance)
                              * content_retention(descendant, ancestor)

    lineage_taint_score = max(contribution(a) for a in ancestors), or 0.0 if
                          there are no ancestors at all

Three real, disclosed design choices, each directly answering one of the six
required test scenarios (Stage 6.7's brief):

1. `severity()` is 0.0 for TRUSTED/RELEASED/UNASSESSED ancestors -- an
   "independent benign memory" or one derived only from clean ancestry
   contributes nothing, exactly as required.
2. `content_retention()` -- lexical (Jaccard) similarity between the
   descendant's own content and the tainted ancestor's content -- is the
   mechanism that distinguishes a "direct poison descendant" (near-verbatim
   copy, retention near 1.0, taint mostly preserved) from a "benign
   transformation of poison" (the descendant's content has diverged
   substantially from the tainted ancestor's, retention near 0.0, taint
   collapses toward 0 regardless of how severe the ancestor's own state was).
   This directly operationalizes "a legitimate memory may be derived from a
   suspicious memory without preserving the malicious content" (Stage 6.7
   brief) as a real, computable quantity rather than an assumption.
3. `max()`, not a sum or average, across multiple ancestors -- a "mixed-origin
   memory" (one TRUSTED parent, one QUARANTINED parent) is judged by its
   WORST real ancestor, not diluted by averaging in a clean one. This
   prevents an attacker from "laundering" a tainted derivation by pairing it
   with an unrelated clean one to dilute the taint score.

Reuses `phase6.defense.retrieval.signals`' own `_tokenize`/`_jaccard_similarity`
for content retention -- the SAME tokenization already vetted and tested there,
not a second, divergent implementation.

WHAT THIS MITIGATION DOES NOT SOLVE (P2 disclosure, 2026-09-14 -- the mirror
image of `retrieval/signals.py`'s own "WHAT THIS MITIGATION DOES NOT SOLVE"
section, which discloses the identical mechanism's identical weakness for D3;
this module reuses that SAME lexical `content_retention()` mechanism for D4
and had not, until this note, disclosed the mirror-image failure mode
separately): `content_retention()` is lexical (Jaccard) similarity, so it
inherits `retrieval/signals.py`'s own disclosed evasion exactly -- a
descendant that PARAPHRASES a tainted ancestor's content, preserving its
malicious intent but changing enough surface wording to fall below what
Jaccard similarity treats as "near-verbatim," gets a `retention` near 0
regardless of the ancestor's severity, so `lineage_taint_score` collapses
toward 0 for that descendant. This is the same structural limitation
`retrieval/signals.py` already names for D3 (clustering/consensus only
catches near-literal repetition; no purely lexical, no-external-verification
mechanism can distinguish a paraphrased-but-still-malicious descendant from a
genuinely independent benign transformation) -- carried forward here as a
real, disclosed D4 limitation, not silently assumed solved because it was
disclosed once for a sibling module. See
`test_lineage_taint_signal_still_evades_via_paraphrase` in
`phase6/tests/test_propagation_containment.py` for the concrete,
non-hypothetical demonstration this note is grounded in, mirroring
`test_paraphrased_coordinated_poison_still_fully_evades_dedup`'s own role for
D3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence

from phase6.defense.policy.records import FORBIDDEN_SIGNAL_KEYS, EvaluatorOnlyLeakageError
from phase6.defense.policy.states import BLOCKED, QUARANTINED, SUSPICIOUS
from phase6.defense.retrieval.signals import _jaccard_similarity, _tokenize

SIGNALS_VERSION = "propagation-signals-1.0.0"

# Uncalibrated v1 severity mapping (disclosed, versioned starting default --
# Stage 6.9's job to calibrate against real development data, per the same
# discipline as every other Phase 6 threshold).
SEVERITY: Dict[str, float] = {
    BLOCKED: 1.0,
    QUARANTINED: 0.7,
    SUSPICIOUS: 0.4,
    # TRUSTED, RELEASED, UNASSESSED are absent -- absence means 0.0 (a
    # KeyError-safe .get(..., 0.0) is used at the call site, so any state
    # this dict does not name is treated as non-tainting by construction,
    # never accidentally tainting via a missing-key crash).
}

# Geometric decay per hop of DERIVED_FROM distance: distance=1 (direct
# parent) -> decay=1.0, distance=2 (grandparent) -> 0.5, distance=3 -> 0.25,
# etc. Uncalibrated v1 default.
DISTANCE_DECAY_BASE = 0.5


def distance_decay(distance: int) -> float:
    if distance < 1:
        raise ValueError(f"distance must be >= 1 (1 = direct parent); got {distance}")
    return DISTANCE_DECAY_BASE ** (distance - 1)


@dataclass(frozen=True)
class AncestorRecord:
    """One real ancestor in a descendant's DERIVED_FROM chain, supplied by the
    caller (Stage 6.10's real wiring would build this from Phase 5's actual
    `build_propagation_graph()` output plus a `GovernanceLedger.current_state()`
    lookup per ancestor -- this module does not read any ledger or graph
    itself, consistent with the plain-data-carrier discipline established for
    `SignalContext` and `RetrievalCandidate`)."""

    memory_id: str
    content_text: str
    security_state: str
    distance: int  # 1 = direct parent, 2 = grandparent, etc.

    def __post_init__(self) -> None:
        if self.distance < 1:
            raise ValueError(f"AncestorRecord.distance must be >= 1; got {self.distance}")


def lineage_taint_signal(
    descendant_content: str, ancestors: Sequence[AncestorRecord]
) -> Dict[str, float]:
    """Compute `{"lineage_taint_score": v}` for one descendant, given its own
    content and its real ancestor chain. Returns 0.0 for a descendant with no
    ancestors, or whose entire ancestor chain is TRUSTED/RELEASED/UNASSESSED.

    Manually leakage-checked (not `@signal_function`-wrapped) because this
    signal is a function of a descendant's content plus a SEQUENCE of
    ancestor records, not a single `SignalContext` -- the same accepted
    pattern already used for the pool-level retrieval consensus signal.
    """
    if not ancestors:
        score = 0.0
    else:
        descendant_tokens = _tokenize(descendant_content)
        contributions = []
        for ancestor in ancestors:
            severity = SEVERITY.get(ancestor.security_state, 0.0)
            if severity == 0.0:
                contributions.append(0.0)
                continue
            retention = _jaccard_similarity(descendant_tokens, _tokenize(ancestor.content_text))
            contributions.append(severity * distance_decay(ancestor.distance) * retention)
        score = max(contributions)

    signal = {"lineage_taint_score": score}
    offending = set(signal.keys()) & FORBIDDEN_SIGNAL_KEYS
    if offending:  # unreachable given the fixed key name, kept for parity/defense-in-depth
        raise EvaluatorOnlyLeakageError(f"lineage_taint_signal leaked {offending!r}")
    return signal
