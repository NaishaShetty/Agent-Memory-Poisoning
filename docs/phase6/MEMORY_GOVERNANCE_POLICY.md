# Memory Governance Policy (MGP) — v1

Status: 6.3 deliverable. This is native MAMBench design work — the 6.2 gap analysis
found no external defense implements a persisting, propagating trust state (D2), so
this document is not a reproduction of anything and its claims stand or fall on
Phase 6's own future validation (Stage 6.9 ablation, Stage 6.16 utility regression),
not on borrowed authority. The six candidate states and six candidate actions the
original Phase 6 brief proposed are evaluated below, not frozen by assumption.

---

## 1. Relationship to Phase 3's Memory Lifecycle (non-negotiable boundary)

Phase 3's `memory_versioning.py` already defines a lifecycle status
(`active` / `superseded` / `retired`) that governs which version of a memory identity
is current. **MGP's security state is a completely separate field, on a completely
separate, Phase-6-native ledger, keyed by the same canonical `memory_id` Phase 3
already assigns.** It is never written into `CanonicalMemoryLedger` or
`CanonicalEventLedger`, never read by any Phase 3 function, and never substitutes for
Phase 3's own status. A memory can be simultaneously `lifecycle_status=active` (Phase
3) and `security_state=QUARANTINED` (Phase 6) — these two facts answer different
questions ("which version is current" vs. "should this be trusted") and neither
phase's code needs to know the other's vocabulary exists. This separation is the
literal instruction in the Phase 6 brief and is treated here as an architectural
invariant, tested directly (Section 7).

## 2. Security State Model

### 2.1 Evaluating the six candidate states

The brief proposed: `UNASSESSED, TRUSTED, SUSPICIOUS, QUARANTINED, BLOCKED, RELEASED`.
Each is checked against a real need before being frozen:

- **UNASSESSED** — needed. A memory can exist in Phase 3's ledger before any Phase 6
  defense component has ever evaluated it (e.g., MGP is deployed after some memories
  already exist, or a component is disabled in an ablation condition B0–B3). Without
  this state, "no state" and "positively judged trustworthy" would be indistinguishable
  — a real gap the state model must not silently collapse.
- **TRUSTED** — needed. The positive outcome of a D1 (or later D3) assessment that
  found nothing suspicious. This is the default resting state for the large majority
  of real benign memories and must exist so a defense doesn't have to keep
  re-justifying every retrieval of ordinary content.
- **SUSPICIOUS** — needed. An intermediate state distinct from both TRUSTED and
  QUARANTINED: content is still eligible for retrieval (unlike QUARANTINED) but
  carries a flag that D3 can use to downrank or annotate it. This is what makes
  `ALLOW_WITH_RESTRICTION` and `DOWNRANK` meaningfully different from a binary
  allow/block policy, and is required by Stage 6.9's action-vs-effect ablation design
  (a policy that only ever chooses TRUSTED or BLOCKED cannot express "somewhat
  concerning but not concerning enough to exclude," which the brief's action list
  explicitly wants distinguished).
- **QUARANTINED** — needed. Persisted, excluded from retrieval eligibility, but not
  deleted — this is the state that makes Stage 6.7's requirement ("a legitimate memory
  may be derived from a suspicious memory without preserving malicious content" /
  "do not blindly assume transitive quarantine is correct") actually testable: a
  quarantined memory must remain inspectable (for the six D4 test scenarios) rather
  than vanish.
- **BLOCKED** — needed, but scoped precisely: BLOCKED means "this content will never
  be exposed to the agent," decided either at admission (content never persisted at
  all — in which case BLOCKED is a terminal *decision record*, not a state on a
  stored memory, since there is no memory identity to attach a state to) or after
  quarantine review found strong evidence against release (content persisted, marked
  BLOCKED, permanently excluded from retrieval but never deleted, preserving evidence
  for Stage 6.18 failure analysis).
- **RELEASED** — needed, and kept **distinct from TRUSTED** rather than collapsed
  into it. A RELEASED memory has been QUARANTINED at some point and later cleared;
  keeping this distinct from a memory that was TRUSTED from the start preserves the
  governance history needed for Stage 6.9 (did quarantine correctly release benign
  items, or did it release something it shouldn't have) and Stage 6.18 (failure
  analysis needs to distinguish "we got this right eventually" from "we never
  flagged it").

**Verdict: all six states are retained, unmodified from the brief's proposal.** No
additional state is introduced for v1; if Stage 6.5–6.9 empirical work later finds a
real need (e.g., a distinct state for "quarantined pending automated re-check" vs.
"quarantined pending human review"), that is an explicitly authorized v2 addition,
not assumed here.

### 2.2 State Transition Table

| From \ To | UNASSESSED | TRUSTED | SUSPICIOUS | QUARANTINED | BLOCKED | RELEASED |
|---|---|---|---|---|---|---|
| UNASSESSED | — | ✓ (D1 clean) | ✓ (D1 flags) | ✓ (D1 strong flag) | ✓ (D1 admission block) | — |
| TRUSTED | — | — (no-op) | ✓ (D3/D4 later finds anomaly) | ✓ (escalation) | — (must pass through SUSPICIOUS/QUARANTINED first — see rationale) | — |
| SUSPICIOUS | — | ✓ (corroborating evidence clears it) | — (no-op) | ✓ (escalating evidence) | — | — |
| QUARANTINED | — | — (must resolve via RELEASED, not directly) | — | — (no-op) | ✓ (review confirms malicious) | ✓ (review clears it) |
| BLOCKED | — | — | — | — | — (terminal) | — |
| RELEASED | — | — | ✓ (new evidence re-raises concern) | ✓ (re-quarantine) | — | — (no-op) |

Rationale for the non-obvious edges:
- **TRUSTED cannot jump directly to BLOCKED.** A memory that was positively assessed
  and later implicated (e.g., discovered downstream via D4 propagation evidence) must
  pass through SUSPICIOUS or QUARANTINED first. This is a deliberate design choice,
  not an oversight: it guarantees every BLOCK decision has an intermediate,
  independently-timestamped SUSPICIOUS/QUARANTINED record in its history, which
  Stage 6.18's failure analysis needs to reconstruct "how much warning did we have
  before we blocked this" — a direct TRUSTED→BLOCKED edge would erase that evidence
  trail.
- **QUARANTINED cannot jump directly to TRUSTED.** It must resolve through RELEASED,
  which (per 2.1) preserves the fact that it was once quarantined. This is what makes
  RELEASED a distinct, non-collapsible state rather than a redundant alias for
  TRUSTED.
- **BLOCKED is terminal for v1.** No transition out of BLOCKED is defined. This is a
  disclosed, conservative design choice, not a claim that a blocked memory can never
  legitimately be wrong — if Stage 6.18's failure analysis later finds a real false
  BLOCK that needs reversal, that is a v2 addition requiring its own justification,
  not something this policy pre-authorizes silently.
- **RELEASED can be re-flagged** (→ SUSPICIOUS or QUARANTINED). Release is not a
  permanent guarantee; new evidence (e.g., a later D4 propagation finding) can
  re-open the question. This is required for Stage 6.7's containment scenarios to be
  testable in both directions.

## 3. Action Vocabulary

The brief's six actions — `ALLOW, ALLOW_WITH_RESTRICTION, DOWNRANK, QUARANTINE,
BLOCK, REQUIRE_VALIDATION` — are retained, but split explicitly by **whether the
action changes persisted state (D2) or only affects one retrieval call (D3-local)**,
because conflating these two was identified in the 6.2 audit as a real ambiguity in
how "action" is used loosely across the literature. A seventh action, `RELEASE`, is
added beyond the brief's original six: Section 2's state model requires a QUARANTINED
→ RELEASED transition (Section 2.1's justification for keeping RELEASED distinct from
TRUSTED depends on it), and no action in the brief's original list names that
transition. This is a disclosed, minimal, necessary addition — not scope creep — since
the alternative would be an unreachable state in the very model that motivated it.

| Action | Scope | State transition it can cause | Layer |
|---|---|---|---|
| `ALLOW` | Persistent | UNASSESSED → TRUSTED | D1 |
| `ALLOW_WITH_RESTRICTION` | Persistent | UNASSESSED/TRUSTED/RELEASED → SUSPICIOUS | D1 or D3 (escalation) |
| `REQUIRE_VALIDATION` | Persistent | UNASSESSED/TRUSTED/RELEASED → SUSPICIOUS (held pending further evidence — same resulting state as `ALLOW_WITH_RESTRICTION`, but the decision record's `reason` field distinguishes "downranked because of weak signal" from "held because signal is inconclusive," which matters for Stage 6.18's failure taxonomy even though the state machine does not) | D1 or D2 |
| `QUARANTINE` | Persistent | SUSPICIOUS/TRUSTED/RELEASED → QUARANTINED | D1 (strong signal) or D2 (escalation from later evidence) |
| `BLOCK` | Persistent | UNASSESSED → BLOCKED (pre-admission) or QUARANTINED → BLOCKED (post-review) | D1 or D2 |
| `RELEASE` | Persistent | QUARANTINED → RELEASED | D2 (review/validation resolves a quarantine as benign) |
| `DOWNRANK` | **Query-local, non-persistent** | None — this is a scoring adjustment applied within one retrieval call's candidate ranking, not a write to the security-state ledger. A memory can be DOWNRANKed in one query's candidate pool (e.g., because D3's consensus check flagged unusual agreement in that specific pool) without its persistent state changing at all. | D3 |

This split matters scientifically: Stage 6.9's ablation needs to isolate "does
persisting a security state help" (D1/D2 effect) from "does per-query re-scoring
help" (D3-local effect) — collapsing DOWNRANK into the same bookkeeping as QUARANTINE
would make that ablation impossible to interpret cleanly.

## 4. Decision Record (the persisted evidence trail)

Every MGP decision — whether it changes persisted state or is a query-local DOWNRANK
— is recorded, append-only, on a Phase-6-native ledger (`GovernanceLedger`, Section
6). No decision is ever silently made and left unrecorded; no decision is ever
overwritten. Required fields (mirroring the brief's Stage 6.5 requirement exactly):

```
candidate_memory_id   — the real, deterministic Phase 3 memory identity this decision concerns
decision_id           — content-derived identifier (Section 6), never a random UUID
policy_version        — which MGP policy version produced this decision (Section 5)
signals_used          — which named signals were evaluated and their raw values (never
                         just a final score — Stage 6.18 needs to reconstruct WHY)
action                — one of the six actions in Section 3
resulting_state       — the security state after this decision (or `None` for a
                         query-local DOWNRANK, which changes no persisted state)
reason                — a short, evidence-grounded natural-language explanation,
                         generated FROM signals_used, never fabricated independently
run_id / episode_id   — Phase 5's own identity hierarchy, reused verbatim (no new
                         identity scheme invented)
timestamp             — wall-clock, for human audit only; never used for ordering
                         logic (ordering uses the append-only ledger sequence itself,
                         consistent with Phase 3/5's own determinism discipline)
evidence_refs         — references to the real Phase 3/5 events that grounded this
                         decision (e.g., a specific CanonicalEvent id, a specific
                         Phase5Event id) — never a bare claim with nothing to point to
```

## 5. Policy Versioning

`policy_version` is a plain string constant (e.g. `"mgp-1.0.0"`), read from one
source-of-truth module constant — mirroring Phase 2's own reproducibility discipline
(Methodology §8: "every version value... read from its single source-of-truth
constant"). Any change to the state machine (Section 2.2), the action vocabulary
(Section 3), or a signal's threshold requires a version bump. A decision record's
`policy_version` is what lets Stage 6.14 (adaptive attacker) and Stage 6.15
(leave-one-attack-out) prove a threshold was frozen before evaluation, not tuned on
the held-out case (Rule 14).

## 6. GovernanceLedger — Storage Model

Additive, append-only, Phase-6-native (never a modification to `CanonicalEventLedger`
or `Phase5EventLedger`). Structurally mirrors the append-only discipline both of
those ledgers already use — reusing the *pattern*, not the *code*, since neither
ledger's schema has room for MGP's fields without a frozen-schema violation.

- **Identity**: `decision_id` is a SHA-256 hash over the ordered tuple
  `(candidate_memory_id, policy_version, signals_used, action, run_id)` — deterministic,
  collision-free, mirroring Phase 1's own memory-record identity discipline
  (Methodology §5.2/§8). Two identical decisions (same memory, same policy, same
  signals, same run) produce the same `decision_id`; this makes accidental duplicate
  recording detectable rather than silently doubling evidence.
- **Current-state lookup**: `current_state(memory_id) -> SecurityState` is a pure
  function over the append-only log (fold over all decisions for that memory_id in
  ledger order), never a separately mutated "current state" field that could drift
  from the decision history — the same "projection, never a second store" discipline
  Phase 5's `assemble_trace()` already uses.
- **No deletion**: `GovernanceLedger` has no delete or update operation. A wrong
  decision is corrected by appending a new decision with a `reason` that says so, not
  by editing history (Rule 16/18: don't overwrite historical evidence, don't hide
  failures).

## 7. Evaluator-Only Leakage Boundary (restated here, enforced in code)

No field on `MGPDecisionRecord`, `signals_used`, or `evidence_refs` may ever be
populated from: `attack_id`, `attacker_originated`, any of the nine ground-truth
states beyond the raw event that produced them, a `counterfactually_influential`
event, or the literal Sleeper trigger phrase. This is checked by a real test
(`test_governance_policy.py`, Section 8) that constructs a decision using a
deliberately evaluator-only-tainted signal dict and asserts the ledger's write path
rejects it — not merely asserted in prose.

## 8. What 6.3 Does NOT Decide

- The actual signal functions that produce `signals_used` values (SENTINEL-derived
  content heuristics, A-MemGuard-style consensus checks, the D2 lineage-based signal
  for descendants) — that is Stage 6.4 (Signal Contract) and 6.5–6.7 (component
  implementation).
- Numeric thresholds for any action (e.g., at what heuristic score `ALLOW_WITH_RESTRICTION`
  becomes `QUARANTINE`) — thresholds are frozen only after real development-data
  calibration (Section 5; Rule 14), not invented here.
- How D4 propagates state to descendants — Section 2's table intentionally does not
  include an automatic ancestor→descendant transition, because Stage 6.7 explicitly
  requires that a descendant's own state be independently assessed (with the
  ancestor's state as one input signal among several, never an automatic
  relabeling) — full design deferred to Stage 6.7.

## 9. Verdict

**PASS** as a 6.3 deliverable. All six states and six actions are retained after
being individually justified rather than assumed; the transition table is
non-trivial in a way that is defensible against the actual Stage 6.7/6.9/6.18
requirements it must support; the Phase 3 lifecycle boundary is architecturally
enforced (separate ledger, separate identity join, no shared mutation path); the
evaluator-only boundary is stated precisely enough to be tested, not just asserted.
