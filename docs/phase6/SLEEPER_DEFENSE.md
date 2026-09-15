# Stage 6.8 — Sleeper/Dormant Poison Defense

Status: 6.8 deliverable summary (design rationale in `phase6/defense/sleeper/`
module docstrings; this document is the stage-gate record).

## Objective

Handle dormant, document-embedded write-instruction content (Sleeper Memory
Poisoning's own documented mechanism, Methodology Section 17.3) across its full
lifecycle — before activation, near/at activation, after activation — **without
ever being given the actual trigger phrase as a shortcut**. The defense must work
from the same legitimately-available signal categories every other Phase 6
component uses, not evaluator-only knowledge of what makes this specific attack's
payload special.

## What Was Implemented

Two structural properties follow directly from Sleeper's own documented
mechanism ("a document-embedded instruction that commands a memory/bio write,
remaining dormant... until a later, semantically related query activates it"),
neither requiring the actual trigger phrase:

- `phase6/defense/sleeper/signals.py` — `imperative_write_directive_signal()`:
  detects the STRUCTURAL PATTERN any such payload must exhibit — a persistence
  marker ("from now on," "in future conversations," "for future reference")
  **combined with** a response-directive verb ("always say," "treat this as
  confirmed," "make sure to tell"). Requiring both together (not either alone)
  is what keeps this signal off ordinary conditionals and personal reminders,
  which typically carry only one of the two components. **These regex patterns
  were validated against real true/false-positive examples before being
  shipped** — 4 constructed true positives modeled on the attack's documented
  mechanism, 6 constructed false positives (an ordinary reminder, an ordinary
  conditional, a general value statement, a plain note, a persistence-marker-
  only sentence, a directive-verb-only sentence) — all classified correctly on
  the first validated iteration, and all six now permanent regression tests.
- `dormancy_activation_signal()`: a real, legitimately-available signal
  (Signal Contract Section 2.3 — retrieval frequency within a run), never the
  evaluator-only 3-state dormancy classifier `phase4/shared/dormancy_report.py`
  already defines for campaign reporting (confirmed by direct inspection that
  this module never imports it).
- `phase6/defense/sleeper/sleeper_guard.py` — two decision points matching the
  attack's own two-phase structure: `evaluate_sleeper_admission()` (write-time,
  content signal only) and `evaluate_sleeper_retrieval_risk()` (retrieval-time,
  **multiplicatively gated**: `directive_score × dormancy_score`). The
  multiplicative gate is the key design choice — `dormancy_activation_score`
  alone (a memory simply being retrieved for the first time, which is
  completely ordinary for the vast majority of real memories) can never trigger
  anything on its own; only the *combination* of directive-structured content
  and first-activation-shaped retrieval timing does.

## A Real Bug Found and Fixed Before Shipping

An early draft of `evaluate_sleeper_retrieval_risk()` mapped any nonzero gated
score below the `DOWNRANK` band to a persistent `ALLOW_WITH_RESTRICTION` action
— meaning a single regex match on content that had already been safely retrieved
many times before (and therefore had a tiny, decayed dormancy score) would still
silently write a persistent `SUSPICIOUS` state. This was caught before shipping
(not discovered later by a test failure) by re-reading the logic against its own
stated intent, and fixed: below the `DOWNRANK` threshold, the action is plain
`ALLOW`, no persistent state change. The corrected version is what the shipped
code and its tests reflect — this is disclosed here rather than presented as if
the design were correct on the first attempt.

## Both Decision Layers Cap at QUARANTINE, Never BLOCK

Same discipline as Stage 6.7's propagation containment, for an analogous reason:
a single regex-based structural heuristic — however validated on its own test
set — is treated as weaker evidence than Stage 6.5's multi-signal corroboration,
which remains the only path to `BLOCK`.

## Required Scenarios — All Covered, Each With a Distinct, Correct Outcome

| Scenario | Setup | Result |
|---|---|---|
| Dormant poison before activation | Directive content, admission-time | `QUARANTINE` (persistent) |
| Poison at activation | Directive content, first retrieval (prior_count=0) | `QUARANTINE` (gated score = 1.0) |
| Poison near activation | Directive content, prior_count=3 | `DOWNRANK` (query-local, gated score = 0.25) |
| Poison after activation | Directive content, prior_count=20 | `ALLOW` (gated score ≈ 0.048 — by this point a real pipeline would already have quarantined it at first activation; this reflects the signal's own natural decay if that hadn't happened) |
| Benign dormant-looking memory | No directive pattern, prior_count=0 (maximal dormancy) | `ALLOW` — dormancy alone never fires |
| False trigger condition | Ordinary conditional language | `ALLOW` — no persistence+directive combination |
| Semantically similar benign memory | Same topic (assistant behavior), not a directive | `ALLOW` — structural pattern absent despite topical similarity |

## Tests and Evidence

23 tests: content-signal true/false positives (including the "requires both
components" isolation test), dormancy-signal monotonic decay, all seven required
scenarios above, determinism, a legal-no-op transition check (`QUARANTINED →
QUARANTINED`), and static checks that this module never imports Phase 4's
dormancy classifier or Phase 5 directly, and never hardcodes an attack name or
literal reference to this project's real Sleeper campaign content.

**Full Phase 6 suite: 151 passed, 0 failed** (128 from Stages 6.3–6.7, plus 23
new for Stage 6.8). Frozen `phase3/`, `phase4/`, `phase5/`, `attribution/`
verified unchanged.

## Limitations Carried Forward

1. The directive-pattern regex, like Stage 6.6's lexical consensus signal, is a
   crude, interpretable proxy — validated on a small, hand-constructed test set
   (4 true positives, 6 false positives), not a real corpus at scale. A more
   sophisticated attacker paraphrasing the directive structure itself (e.g.,
   splitting the persistence marker and response verb across separate sentences,
   or using synonyms this regex set doesn't cover) would evade it — the same
   class of limitation already tracked for the lexical retrieval signal in
   `STAGE_6_9_QUEUE.md`, not newly discovered here.
2. `evaluate_sleeper_admission()` only ever fires on content containing an
   explicit English-language directive structure — it has no mechanism for a
   payload that achieves the same effect through other means (e.g., a
   non-imperative but still effectively-triggering framing). This is a
   disclosed scope boundary, not a claim of general dormant-trigger detection.
3. Thresholds (`ADMISSION_THRESHOLD_QUARANTINE`, `RETRIEVAL_THRESHOLD_QUARANTINE`,
   `RETRIEVAL_THRESHOLD_ALLOW_WITH_RESTRICTION`) are disclosed, uncalibrated v1
   defaults, not validated against real MAMBench Sleeper campaign content —
   real calibration is Stage 6.9's job, per the same discipline as every other
   Phase 6 threshold.
4. This module does not itself read any real ledger — `prior_retrieval_count`
   and `current_security_state` must be supplied by the caller from real
   `EventRunMembershipLedger`/`GovernanceLedger` state. That wiring is Stage
   6.10's integration job.

## Verdict

**PASS** as a 6.8 deliverable. All seven required scenarios produce distinct,
correct outcomes; the trigger-phrase-independence requirement is verified by
static analysis, not just asserted; the content-detection regex was validated
against real false-positive examples before shipping rather than assumed
correct; and one real design bug (a nonzero-score-always-escalates error) was
found and fixed during development, disclosed here rather than silently
corrected.
