# Stage 6.18 — Defense Failure Analysis

Status: 6.18 deliverable. A synthesis of every real failure and limitation
found across Stages 6.5–6.17, reconstructed through the full lifecycle and
classified against the brief's own F1–F14 taxonomy — plus one disclosed,
clearly-labeled extension this synthesis found necessary.

---

## 1. Method

`phase6/evaluation/failures/catalog.py` — 13 real cases, each a
`FailureCase` with a mandatory, non-empty lifecycle reconstruction, an
earliest-possible-intervention judgment, a primary (and where relevant
secondary) F-code classification, and `evidence_refs` pointing to the real
test or document that already established the finding. **No new failure was
invented for this stage** — every case traces to work already done in
Stages 6.5–6.17, and a real test
(`test_test_function_evidence_refs_actually_exist`) verifies every test-style
citation actually names a real, existing test rather than a fabricated one.

## 2. The One Disclosed Taxonomy Extension — F15

Reconstructing AgentPoison's failure (`FC-06`) exposed a real gap in F1–F14:
F2 ("poison hidden from admission detector") implies a detector *exists* and
*failed to catch* something. AgentPoison's real attack surface — a query-side
embedding trigger — has **no Phase 6 mechanism examining it at all**. Nothing
failed to detect it; nothing was ever looking. Rather than force this into F2
(which would misrepresent a structural absence as a detection miss), this
stage adds **F15 — no applicable mechanism (proposed extension)**, used
sparingly and only for the two cases (`FC-06`, and `FC-10`'s aggregate
seven-attack result, which inherits it as a secondary cause for the same
reason) that actually describe this specific structural gap — verified by a
real test (`test_f15_extension_used_only_for_the_agentpoison_style_structural_
gap`), not left to drift into a catch-all.

## 3. Summary Statistics (real, computed)

**13 total cases: 10 unresolved, 3 resolved.**

| Primary cause | Count | Cases |
|---|---|---|
| F2 — poison hidden from admission detector | 4 | FC-04, FC-07, FC-09, FC-10 |
| F4 — poison selected | 1 | FC-01 |
| F6 — poison propagated | 1 | FC-08 |
| F9 — benign memory incorrectly classified | 1 | FC-02 |
| F11 — defense evidence unavailable | 1 | FC-05 |
| F12 — defense policy conflict | 3 | FC-03, FC-11, FC-12 |
| F14 — environment/infrastructure failure | 1 | FC-13 |
| F15 — no applicable mechanism (extension) | 1 (+1 secondary) | FC-06 (+FC-10) |

**F2 dominates** — four of thirteen cases, all involving content-based
signals (admission or Sleeper) failing against realistic or deliberately
adapted phrasing. This is the single most common, most consistent failure
mode found across this entire project's Phase 6 work, corroborating (not
merely repeating) Stage 6.14's and 6.15's own conclusions with a structured
count.

## 4. The Three Resolved Cases — Real Fixes, Not Erasure

- **FC-11** (Stage 6.8): a nonzero-gated-score-always-escalates bug, caught
  and fixed *before shipping* — the earliest possible intervention point, by
  definition.
- **FC-12** (Stage 6.7): the documented, intentional `QUARANTINED → ALLOW`
  illegal-transition behavior — resolved by design, not by accident.
- **FC-03** (Stage 6.9, Item 2): the external-corroboration amplification
  risk — resolved by the decision *not to adopt* the mechanism, found during
  analysis-before-implementation rather than after deployment.

All three are kept in the catalog rather than removed, per Rule 17 (don't
delete negative results) — a resolved case is still real evidence of how the
resolution was reached.

## 5. The Ten Unresolved Cases — Grouped by What Would Actually Fix Them

- **Content-signal redesign needed** (FC-04, FC-05, FC-07, FC-09, FC-10):
  four to five cases where the fix is not a threshold adjustment but a
  fundamentally different signal design — semantic rather than purely
  lexical/regex detection, an idea Stage 6.6 already partially explored (D2)
  without full success at the decision layer (Stage 6.6/6.9's own honest
  finding).
- **Structural gap, no existing mechanism to extend** (FC-06, and FC-10's
  secondary cause): AgentPoison's query-side trigger surface would need an
  entirely new component class Phase 6 has never attempted.
- **Lexical blind spot transferring across layers** (FC-01, FC-08): the same
  underlying weakness (token-overlap similarity) affects both D3 (retrieval)
  and D4 (propagation) — a fix to the shared `dedup_consensus.py`/lexical
  primitive would address both simultaneously, rather than needing two
  separate fixes.
- **A real, disclosed engineering bug, not yet fixed in the shipped default**
  (FC-02): the diverse-benign-pool 100% false-positive rate — a fix (the
  min-cluster-size gate) exists and is validated (Stage 6.9/6.16) but not yet
  adopted as the shipped default, pending separate authorization.
- **Infrastructure precondition, not a defense-logic failure** (FC-13): no
  fix is possible from within Phase 6's own code — this requires the
  environment blocker (missing `mem0ai`, unreachable LLM server) to lift.

## 6. Tests and Evidence

13 tests (`test_failure_analysis.py`): catalog integrity (unique ids,
non-empty lifecycle/evidence, no primary/secondary duplication), the F15
extension's disclosed, narrow scope, resolved-case bookkeeping matching the
real three cases, summary arithmetic, and — the most safety-critical test in
this file — confirmation that every test-style evidence citation names a
real, existing test function in this repository, not a fabricated reference.

**Full Phase 6 suite: 279 passed, 0 failed.** Frozen `phase3/`, `phase4/`,
`phase5/`, `attribution/` verified unchanged.

## 7. Limitations Carried Forward

1. This catalog synthesizes *known* failures — it cannot claim completeness
   over failure modes not yet discovered (e.g., MINJA/MemoryGraft's real,
   as-opposed-to-synthetic, injected content has never been located, per
   Stage 6.10/6.15's own disclosed gap; a real such case might reveal new
   failure patterns this catalog doesn't yet contain).
2. F15's status as a genuine taxonomy gap (not just this project's
   preference) is this stage's own judgment — a different research team
   might argue AgentPoison's case still fits F2 under a looser reading. The
   disclosed reasoning for the extension is given so a reader can evaluate
   that judgment rather than take it on faith.
3. No case in this catalog involves F1 (poison admitted) as a *sole* primary
   cause in the sense of "the defense saw evidence and wrongly allowed it" —
   every F2-classified case is more precisely "the defense had no signal to
   act on," a distinction preserved rather than collapsed.

## Verdict

**PASS** as a 6.18 deliverable. Every case reconstructs the real lifecycle
rather than reporting "defense failed," names the earliest point a mechanism
could plausibly have intervened (including "no such point exists yet" where
that is honestly the case), and one real taxonomy gap was found and disclosed
as an extension rather than forced into an ill-fitting existing code.
