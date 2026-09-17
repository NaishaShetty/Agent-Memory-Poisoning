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

**Update (2026-09-17):** a further 9 tests were added in a separate file,
`phase6/tests/test_sleeper_age_gate.py` (deliberately not merged into this
stage's own frozen test file — see that file's own docstring), covering the
`age_based_dormancy_gate_signal()` / `as_of_timestamp` fix described in the
Update above. **Full Phase 6 suite as of this update: 327 passed, 0 failed.**

**Further update (same day):** `imperative_write_directive_signal()`'s
persistence-marker regex was broadened (`signals.py`'s own Update note) after
finding it missed a real, conditional "if"/passive-"asked" framing 3 of the
real B0-B7 ablation corpus's own 5 Sleeper-family poison scenarios use.
`phase6/tests/test_sleeper_persistence_regex_broadening.py` (7 more tests)
locks in both the fix and the non-regression against every existing
true/false-positive fixture. Real, measured ablation effect: `SLEEPER_ONLY`'s
own Sleeper-family detection rose from 40% to 100%; combined with the other
2026-09-17 fixes, B8 (all four layers) rose from 61.8% to 70.6% overall
poison detection, at the SAME 7.3% false-positive rate
(`docs/phase6/PHASE6_RESULTS.md`'s own Update has the full account).

## Limitations Carried Forward

1. The directive-pattern regex, like Stage 6.6's lexical consensus signal, is a
   crude, interpretable proxy — validated on a small, hand-constructed test set
   (4 true positives, 6 false positives), not a real corpus at scale. A more
   sophisticated attacker paraphrasing the directive structure itself (e.g.,
   splitting the persistence marker and response verb across separate sentences,
   or using synonyms this regex set doesn't cover) would evade it — the same
   class of limitation already tracked for the lexical retrieval signal in
   `STAGE_6_9_QUEUE.md`, not newly discovered here. **Update (2026-09-17):**
   the persistence-marker half was widened once (an "if"/passive-"asked"
   conditional framing a real ablation scenario used but the original regex
   missed — see the Update above), re-validated against the same original
   true/false-positive set with none regressing. This narrows, but does not
   remove, this limitation: it is one disclosed gap closed by direct
   evidence, not a claim that every synonym/paraphrase gap is now covered.
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

   **Update (2026-09-17, Phase 8.9 calibration study,
   `phase8/detection/sleeper_threshold_calibration_study.py`):** a real attempt
   at this calibration found a stronger, mathematical result, not merely that
   the current 0.5/0.2 defaults happen to be imprecise. Because
   `gated_score = directive_score × dormancy_activation_score` and
   `dormancy_activation_score(0) == 1.0` by construction, a brand-new,
   genuinely legitimate persistent-policy memory (structurally
   directive-matching, e.g. a real customer-service return-policy statement)
   scores `1.0` — strictly MORE suspicious — on its very first-ever query than
   the real Sleeper campaign artifact scored (`0.5`) at its own real,
   measured moment of activation (Phase 7/8's own cross-signal trial: first
   selected at `prior_retrieval_count == 1`). Since `1.0 > 0.5`, no threshold
   `T ∈ (0, 1]` can flag the real attack (`T ≤ 0.5`) without also flagging
   every brand-new legitimate directive-matching memory (`1.0 ≥ T` trivially).
   **No choice of these two threshold constants can close this gap** — the
   false-positive risk is forced by using raw retrieval COUNT as the
   dormancy proxy, since a memory's count is identically zero whether it was
   created a second ago or has sat untouched for months. Closing it for real
   would require swapping in a different real signal already available in
   this codebase — Phase 8's `real_dormancy_window()`
   (`phase8/detection/sleeper_dormancy_window.py`), which measures real
   elapsed time/tasks since admission rather than raw retrieval count, and so
   can distinguish "created seconds ago, queried immediately" (short window)
   from "admitted long ago, never touched until now" (long window) — a real
   architecture change to this module's retrieval-time signal composition,
   not a threshold-value change. Not attempted here; disclosed for whoever
   picks this up next.

   **Update (2026-09-17, real fix implemented):** the age/time-since-creation
   signal proposed above was implemented — `age_based_dormancy_gate_signal()`
   (`phase6/defense/sleeper/signals.py`), a real elapsed-time-since-`creation_
   timestamp` signal (Signal Contract Section 2.2, already sanctioned), and a
   new OPTIONAL `as_of_timestamp` parameter on `evaluate_sleeper_retrieval_
   risk()` (`phase6/defense/sleeper/sleeper_guard.py`), defaulting to `None` =
   the exact prior behavior (every existing test in `test_sleeper_defense.py`
   passes unmodified).

   The fix is deliberately NARROWER than "multiply a third decaying factor
   into `gated_score`": a first, naive multiplicative attempt was tried and
   then rejected, because it was verified by direct computation to also
   discount the real attack's own real activation point (`gated_score = 0.5`
   at `prior_retrieval_count == 1`, per Stage 8.6) below the QUARANTINE
   threshold — any third factor `< 1.0` applied on top of an already-exactly-
   at-threshold score pushes it under, which would have traded the false
   positive for a false negative on the real attack. The shipped fix instead
   REPLACES the dormancy component only at the exact point the calibration
   study proved collides — `prior_retrieval_count == 0` — with the real
   age-based score, and leaves `prior_retrieval_count >= 1` (where the real
   Sleeper campaign's own real activation actually occurs) completely
   untouched.

   **Real, measured result** (`phase6/tests/test_sleeper_age_gate.py`, 9
   tests, all passing): a brand-new legitimate directive-matching memory
   queried the instant it is created (`age = 0`, `n = 0`) now correctly
   `ALLOW`s, where it previously always `QUARANTINE`d; the real poison's own
   real activation point (`n = 1`, 2 real minutes after admission, per Stage
   8.6's cross-signal trial) still correctly `QUARANTINE`s, byte-for-byte
   unchanged. **Disclosed residual limitation, not a bug:** legitimate
   directive-matching content that has genuinely sat dormant for a long real
   span before its first-ever query is still `QUARANTINE`d — real dormancy and
   real attack activation are structurally indistinguishable from content and
   timing alone when both are real; this is the same disclosed boundary every
   other Phase 6 single-heuristic signal already carries, not a new one. The
   `as_of_timestamp` parameter is opt-in (Stage 6.10's real-ledger wiring job
   is to actually supply it from a real clock); no existing caller is
   affected until it does.
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
