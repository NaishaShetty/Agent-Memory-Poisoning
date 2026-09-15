# Stage 6.7 — Propagation & Lineage Containment

Status: 6.7 deliverable summary (design rationale in `phase6/defense/propagation/`
module docstrings; this document is the stage-gate record).

## Objective

"Can memory poisoning be contained after the original poisoned memory has already
entered memory?" — specifically: when a memory M2 is `DERIVED_FROM` a suspicious/
quarantined/blocked M1, should M2 automatically inherit M1's suspicion? The brief
is explicit that the answer must not default to "yes" — this stage builds the
mechanism that decides, per descendant, rather than assuming.

## What Was Implemented

- `phase6/defense/propagation/signals.py` — `lineage_taint_signal()`: for a
  descendant and its real ancestor chain (each `AncestorRecord` carrying its own
  already-persisted MGP state, content, and `DERIVED_FROM` distance), computes
  `max(severity(ancestor) × distance_decay(distance) × content_retention)` across
  ancestors. Three deliberate design choices, each answering one required test
  scenario directly:
  - **`content_retention`** (lexical Jaccard similarity between descendant and
    tainted ancestor) is what distinguishes a verbatim "direct poison descendant"
    from a "benign transformation of poison" — taint collapses toward 0 as content
    diverges from the tainted ancestor, regardless of how severe that ancestor's
    own state was. This directly operationalizes "a legitimate memory may be
    derived from a suspicious memory without preserving the malicious content."
  - **`max()`, not average**, across multiple ancestors — a mixed-origin memory
    (one TRUSTED parent, one QUARANTINED parent) is judged by its worst real
    ancestor, so pairing a tainted derivation with an unrelated clean one cannot
    dilute the score.
  - **Distance decay** (geometric, 0.5 per hop) — a grandparent's taint matters
    less than a direct parent's, an interpretable, disclosed default.
- `phase6/defense/propagation/containment_guard.py` — `evaluate_propagation_
  containment()`: maps the taint score to an action via three threshold bands.
  **The strongest possible action is `QUARANTINE`, never `BLOCK`** — enforced by
  an explicit assertion in the code itself, not just a comment, so a future
  threshold edit that accidentally introduced a BLOCK band would fail loudly. This
  is the direct, hard-coded answer to "do not blindly assume transitive quarantine
  is always correct": lineage evidence is treated as strictly weaker than the
  direct content evidence Stage 6.5's admission signals use, which remains the
  only path to `BLOCK`.

## The Six Required Test Scenarios — All Covered, Each With a Distinct Outcome

| Scenario | Ancestor state | Content retention | Result |
|---|---|---|---|
| Direct poison descendant | QUARANTINED | ~1.0 (verbatim) | `QUARANTINE` |
| Benign transformation of poison | QUARANTINED | ~0.0 (unrelated) | `ALLOW` |
| Partial inheritance | QUARANTINED | ~0.4 (moderate) | `ALLOW_WITH_RESTRICTION` |
| Mixed-origin memory | one QUARANTINED + one TRUSTED | high (to the bad parent) | `QUARANTINE` (unaffected by the clean parent) |
| Independent benign memory | none | n/a | `ALLOW`, score exactly 0.0 |
| Legitimate derivation from suspicious-looking-but-benign memory | SUSPICIOUS (weaker) | moderate/low | `ALLOW` or `ALLOW_WITH_RESTRICTION`, never the strongest band |

A seventh test (`test_lineage_alone_never_blocks_even_at_maximum_possible_score`)
pushes every input to its theoretical ceiling (BLOCKED ancestor, distance 1,
verbatim retention — score exactly 1.0) and confirms the action is still
`QUARANTINE`, never `BLOCK` — proving the cap holds even under maximum pressure,
not just in the ordinary cases.

## A Real Edge Case Found and Documented, Not Silently Handled

If a descendant is currently `QUARANTINED` and this guard's own new evidence
computes a low taint score (action would be `ALLOW`), `validate_transition()`
correctly raises `IllegalTransitionError` — Stage 6.3's frozen table requires
`QUARANTINED` to resolve only via `RELEASE`, never a direct `ALLOW`. This is
intentional and tested (`test_reassessing_an_already_quarantined_descendant_with_
low_taint_raises`): this guard evaluates new lineage concern, it is not the
pathway for resolving an existing quarantine. A caller needing to clear a
quarantine based on low current lineage risk must route through an explicit
review/`RELEASE` mechanism, not this function.

## Tests and Evidence

19 tests: all six required scenarios plus the maximum-pressure BLOCK-cap proof,
distance-decay correctness, `max()`-not-average multi-ancestor behavior,
zero-contribution for TRUSTED/RELEASED/UNASSESSED ancestors, evaluator-only
leakage check, the documented QUARANTINED→ALLOW edge case, determinism, and
static checks (no import of Phase 4/5 code directly, no hardcoded attack names).

**Full Phase 6 suite: 128 passed, 0 failed** (109 from Stages 6.3–6.6 + the
semantic-escalation follow-up, plus 19 new for Stage 6.7). Frozen `phase3/`,
`phase4/`, `phase5/`, `attribution/` verified unchanged.

## Limitations Carried Forward

1. `content_retention` reuses the same lexical (Jaccard) tokenizer Stage 6.6's D1
   uses — inherits the same paraphrase blind spot: a descendant that paraphrases
   a tainted ancestor's content heavily enough could score artificially low
   retention despite substantively preserving the malicious claim. This is the
   same class of limitation already tracked in `STAGE_6_9_QUEUE.md` for the
   retrieval consensus mechanism, not a new, separately-tracked issue — a shared
   semantic-vs-lexical calibration question applies here too, and should be
   folded into that queue item's scope when Stage 6.9 addresses it, rather than
   duplicated as a second open item.
2. Severity weights (`BLOCKED=1.0, QUARANTINED=0.7, SUSPICIOUS=0.4`) and distance
   decay (`0.5` per hop) are disclosed, uncalibrated v1 defaults — not validated
   against real MAMBench propagation data.
3. This module does not itself walk Phase 5's real `build_propagation_graph()` —
   it consumes a plain `AncestorRecord` sequence the caller must build from real
   graph output. That wiring is Stage 6.10's integration job, consistent with
   how Stage 6.4 deferred real ledger-reading wiring for every other component.
4. Only `DERIVED_FROM`-style ancestry is modeled (single-parent-chain distance).
   A memory with a more complex provenance graph (e.g. `PRODUCED` relationships,
   or multiple derivation paths to the same ancestor) is not specially handled
   beyond treating each distinct ancestor independently and taking the max —
   sufficient for the six required scenarios, not claimed sufficient for every
   graph topology Phase 5 could produce.

## Verdict

**PASS** as a 6.7 deliverable. All six required scenarios produce distinct,
correct-by-design outcomes; the "never blindly transitive-quarantine" instruction
is enforced as a hard, tested ceiling rather than a soft guideline; and one real
edge case (re-assessing an already-quarantined descendant) was found and
documented as intentional behavior rather than silently left to surprise a later
caller.
