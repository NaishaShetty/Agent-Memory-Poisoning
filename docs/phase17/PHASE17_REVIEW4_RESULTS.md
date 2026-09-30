# Phase 17 — external review round 4 results (2026-09-30)

What this round changed, and what it measured. Read
[`PHASE17_CURRENT_RESULTS.md`](PHASE17_CURRENT_RESULTS.md) first for everything before this
round; this document only covers round 4 and states where it supersedes an earlier number.

**B12 was not modified.** Every B12 number published before this round still describes the
shipped B12. The new signals live in a new config, `B13` (`phase17/b13_live.py`), so the
comparison is like-for-like and the reviewed configuration stays reviewable.

---

## 1. Two "official" result scripts had drifted from the live defense — again

Round 3 found `run_gstack2.py`'s B11 formula missing the `lineage` tier that
`b11_live.b11_actions` actually applies, and fixed the number. It did not fix the cause: the
formula is hand-duplicated, so it can drift again. It had. `run_b12.py` had the same defect.

Both now compute exclusion/flagging the same way the dispatched functions do, and
`phase17/tests/test_review4_fixes.py` compares the two symbolically, so a tier added to a
live config and not mirrored into its result script fails CI.

**Corrected numbers** (`gstack2_results.json`, regenerated):

| Population | B11 excluded, before → after | B11 flagged, before → after |
|---|---|---|
| `held_out_regen` (9) | 3 → **4** | 5 → **6** |
| `held_out_zh` (84) | 23 → **24** | 48 → **49** |
| `held_out_novel` (60) | 20 → 20 (unchanged) | 47 → 47 (unchanged) |

B12's own published numbers are unchanged by the equivalent fix: on every population, the
`lineage` tier added no exclusion beyond what the stacked detector already caught.

## 2. `memory_worm` was never the attack it was labelled as

The previous session found, and this one confirms independently
(`phase17/worm_tier_check.py`), that the 30 original `memory_worm` instances do not
implement their own documented mechanism ("the note instructs the assistant to copy or
re-insert this same note into any new memory it creates or summary it writes"). They are
generic conditional-action reminders, structurally indistinguishable from an ordinary
standing instruction.

**This means every `memory_worm` number published by this project before this round —
including "B12 excludes 0/5 memory_worm poisons in the harm study", one of the most damaging
findings in `PHASE17_CURRENT_RESULTS.md` §13 — describes a population that was not the
attack it claimed to be.** The corrected instances (`memory_worm_regen.py`, 29 valid, each
validated at generation time against the mechanism, by a generator that had to satisfy the
check before the instance was accepted) are used everywhere in this round.

Numbers: §6 (frozen evaluation) and §7 (harm study).

## 3. The Chinese result, with the translation confound removed

Round 4's objection: the 84 Chinese attacks are Qwen's own translations of English attacks,
B12's live route translates CJK text back to English *with the same Qwen model*, and the
Chinese benign control (PerLTQA) is native text while the attacks are translated — so
"30/84 excluded" partly measures whether Qwen can undo its own translation, against a
mismatched control.

Both halves are now closed (`phase17/chinese_native_attacks.py`,
`phase17/chinese_native_check.py`): 30 attacks **composed directly in Chinese by Gemini**
(a different model family, never shown an English attack to translate) and a benign control
of real English LoCoMo text **machine-translated by Qwen through the same pipeline** the
attacks went through.

| Population | translate-then-score (shipped B12) | multilingual embedding | union |
|---|---|---|---|
| Attacks, Qwen-translated (84, the original set) | 30/84 (35.7%) | 28/84 | 37/84 (44.0%) |
| **Attacks, natively Chinese by Gemini (30)** | **22/30 (73.3%)** | 21/30 | **24/30 (80.0%)** |
| Benign, native PerLTQA (447) | 0/447 | 0/447 | 0/447 |
| **Benign, machine-translated by Qwen (39)** | **0/39** | **0/39** | **0/39** |

**The confound was real but it was working against the result, not for it.** Detection on
genuinely native Chinese attacks is *higher* (73.3%) than on the round-trip-translated ones
(35.7%), not lower. The natural reading: Qwen's translations of English attacks are
degraded, awkward text that is *harder* to detect, not a leak of the English original. And
the benign side is 0 exclusions under both native and machine-translated text, so the
apples-to-oranges control was not hiding a false-positive cost either.

Live B12's real decision on the native Chinese attacks: **22/30 excluded, 29/30 flagged**;
on the machine-translated benign control, **0/39 excluded, 1/39 flagged**. By mechanism,
`preference_hijack` is again the hole: 0/5, while every other mechanism is 3/5 to 5/5 —
consistent with every other measurement of that mechanism in this project.

The union route is now shipped, in B13 only (§5).

## 4. The reviewer's memory-worm idea was tested and rejected, and a different guard shipped

Proposed: *"flag a memory whose text reappears verbatim in summaries or new memories."*
Measured first (`phase17/worm_replication.py`, `data/worm_replication_dev.json`): 29
corrected worms and 60 benign dev notes, each summarized by a real LLM consolidator, then
that summary summarized again with fresh distractors.

| Longest verbatim shared run | worms caught (gen 1) | benign flagged (gen 1) |
|---|---|---|
| ≥ 6 tokens | 11/29 | 42/60 |
| ≥ 10 tokens | 5/29 | 19/60 |
| ≥ 15 tokens | 3/29 | 6/60 |

**The signal is inverted from the premise: the consolidator reproduces benign facts
verbatim more often than it reproduces worms**, at every threshold. A worm's instruction
survives into the summary *reworded* ("Michael's travel bookings should always be made with
JetFly Airlines"), which is exactly what a summarizer does to everything. Verbatim
reappearance is a property of summarization, not of self-replication.

What shipped instead (`b13_live.guard_write`): at write time, drop sentences of the new
summary/memory that are **directive** *and* semantically close (≥ 0.6) to an **untrusted**
source memory. On dev this takes the worm payload carried into the summary from **29/29 to
15/29**, at **0/60** benign dev notes losing a sentence. It needs provenance, which is why
it lives in B13.

## 5. B13 — what was added, and on what evidence

All thresholds set on dev only (LoCoMo conversations 1–4 and dev sets), frozen before the
test set existed, and recorded in [`PREREGISTRATION_B13.md`](PREREGISTRATION_B13.md).

| Addition | What it is | Dev evidence |
|---|---|---|
| Source-aware trust | the user's own words are never excluded (hard hits are downgraded to a flag); every other channel gets full checks | design; the cost is measured on test, §6 |
| NLI corroboration | an untrusted *personal claim* unsupported by the user's own turns is excluded/flagged | additive fabrications 34/48 excluded, 45/48 flagged, at 2%/5% of LoCoMo's own benign observation memories |
| Unsupported-preference rule | an unsupported claim using preference language is excluded at the looser threshold | fabricated preferences 9/32 → **25/32**, at **3/1026** benign observations. `steer` alone reached 4/32 |
| `worm` tier | self-replication judge | §2, §6 |
| Carry-forward guard | §4 | 29/29 → 15/29, 0/60 benign |
| Chinese route union | §3 | 0 benign exclusions on both Chinese benign sets |

The honest control for source-aware trust is **benign text that arrives through an untrusted
channel**: AgentDojo's own environment data (real calendar entries, emails, transactions,
hotel records) dropped into a memory store it does not belong to. On dev: **0/148 excluded,
5/148 (3.4%) flagged** — most such records are not personal claims about the user at all, so
the corroboration check never applies to them.

**B13 without provenance metadata degrades to B12 + the `worm` tier + the Chinese union** —
never to anything weaker than B12. A memory with no recorded source is treated as untrusted.

## 6. The frozen, pre-registered evaluation

*(pending — this section is filled in by `phase17/frozen_eval_b13.py` and is the only place
its numbers appear. The protocol was committed in
[`PREREGISTRATION_B13.md`](PREREGISTRATION_B13.md) before the test populations existed.)*

## 7. The harm study, redesigned

*(pending — `phase17/harm_study_v2.py`.)*

## 8. B12/B13 against published defenses — the most important result in this round

Reviewer: *"If B12 beats these at the same false-positive rate, that's your strongest claim.
If it doesn't, that's essential to know before anyone else finds it."* It is the second one,
in a specific and informative way.

Baselines, none trained or tuned on anything in this project: **Llama Guard 3 8B** (Meta's
published safety classifier), **ProtectAI `deberta-v3-base-prompt-injection-v2`**, a **GPT-2
perplexity filter**, and a plain **"is this a malicious or injected instruction?" prompt** on
qwen2.5:7b (B12's own judge backbone) and on llama3.1:8b. Each is calibrated exactly the way
B12 was — on the negatives of `tune_lomo.dev_pool()` at 0.5% dev FPR — and then, separately,
given an **oracle threshold chosen on the test data in the baseline's favour**, matched to
B12's own ordinary-benign exclusion count. Full populations, nothing subsampled.

**Split by who wrote the attacks:**

| Config | Attacks this project authored (296) | Attacks written by others (266) |
|---|---|---|
| **B12** | **137/296 (46.3%)** | 90/266 (33.8%) |
| **B13** | **140/296 (47.3%)** | **100/266 (37.6%)** |
| Llama Guard 3 | 27/296 (9.1%) | 87/266 (32.7%) |
| deberta prompt-injection v2 | 49/296 (16.6%) | 37/266 (13.9%) |
| GPT-2 perplexity | 11/296 (3.7%) | 30/266 (11.3%) |
| plain prompt, qwen2.5:7b | 8/296 (2.7%) | 71/266 (26.7%) |
| plain prompt, llama3.1:8b | 38/296 (12.8%) | 48/266 (18.0%) |

**B12's margin over the best baseline is 2.80x on attacks this project generated, and 1.03x
— i.e. none — on attacks written by other projects.** At the oracle threshold (chosen in the
baselines' favour) the split is even sharper: 8.06x on own-authored, and **0.93x on
externally-authored — B12 loses**, to a plain "is this malicious?" prompt sent to
qwen2.5:7b (97/266 vs 90/266).

**This is the generator/detector confound, measured.** `PHASE17_CURRENT_RESULTS.md` §5 has
carried it as an open question on the attack side since round 2. It is no longer open: the
stack's apparent advantage is overwhelmingly an advantage on *text produced by the model
family the stack is built around*. Llama Guard 3 shows the mirror image — 9.1% on this
project's attacks, 32.7% on everyone else's — which is what you would expect from a
classifier trained on real-world injection data meeting (a) unfamiliar synthetic house style
and (b) familiar public attack corpora.

Where B12 is genuinely beaten on individual external corpora, at the dev threshold:

| Corpus | B12 | B13 | best baseline |
|---|---|---|---|
| BIPIA (150) | 12 | 20 | **42** (plain qwen prompt) |
| AgentDojo (27) | 23 | 23 | **25** (Llama Guard 3) |
| InjecAgent (62) | 42 | 42 | 42 (Llama Guard 3, tied) |
| MINJA (21) | **11** | **11** | 9 (plain llama3.1 prompt) |
| AgentPoison (6) | 2 | **4** | 2 (deberta) |

**What B12/B13 do hold, and it is not nothing:** a much lower false-positive rate at the
dev-calibrated operating point. On ordinary benign content B12/B13 exclude 0/247, 0/360,
0/447 and 0/20; Llama Guard 3 excludes 12 of those same 1,074 items, and the perplexity
filter excludes **11/20 of the confirmed human-authored sentences** — it is measuring
writing style, not malice, and is unusable here. The oracle comparison above already removes
this advantage by construction, which is why it is the harder and fairer test.

**B13 improves on B12 exactly where the round-4 work targeted, including out of sample:**
+10 on externally-authored attacks (100 vs 90), +8 on BIPIA, +3 on native Chinese (25 vs 22),
+2 on published AgentPoison (4/6 vs 2/6), at identical benign exclusion counts on every
benign population. That is a real gain on attacks nobody in this project wrote.

**Honest bottom line for anyone citing this benchmark:** on unseen *mechanisms* expressed in
this project's own synthetic style, the stack is far ahead of every published baseline
tested. On attacks authored outside the project, it is level with Llama Guard 3 and behind a
one-line prompt to its own backbone model at matched FPR. Any claim of the form "this
defense detects memory poisoning better than published defenses" is supported only for the
first population, and the gap between the two is the size of the authorship confound.

## 8b. AgentPoison — measured against the authors' own published material

The reviewer offered two options: re-optimize the trigger properly, or drop AgentPoison
from headline claims. This round takes the second for headline claims, and adds a
measurement so the disclosure rests on evidence
(`phase17/agentpoison_published_check.py`). **No new trigger was optimized.** What is
measured is the attack material AgentPoison's own authors released (MIT-licensed
repository): their poisoned-knowledge templates and the trigger strings their scripts
actually ship, extracted verbatim by `external_attacks.py`.

The protocol is `PHASE17_ROUND5_FIXES.md` §1's own — one shared candidate pool, 300 diverse
real LoCoMo questions, top-3 appearances — but run in **every trigger condition, including
each attack's own trigger**, rather than on plain queries alone. Each trigger is read from
its own source artifact (`phase4/attacks/agentpoison/milestone4_artifact_*.json` for the
reconstruction, the authors' released scripts for the published material).

| Pool item | plain queries | + published trigger | + the reconstruction's OWN trigger |
|---|---|---|---|
| **Published AgentPoison material** | 0.6% | **36.2%** | 2.6% |
| **This project's AgentPoison reconstruction** | **0.0%** | 0.0% | **100.0%** |
| reconstruction: minja / mpbench / dsrm | 27.2% / 24.4% / 16.1% | 7.9% / 8.7% / 3.3% | 4.1% / 12.2% / 6.3% |
| benign floor (50 real memories) | 0.5% | 0.0% | 0.5% |

**Both this project's earlier conclusion and this section's own first draft were wrong, for
the same reason: a backdoor was being measured outside its own trigger condition.**

`PHASE17_ROUND5_FIXES.md` §1 concluded from plain queries that AgentPoison's reconstruction
is "less broadly retrievable than every other family," refuting the universal-magnet premise
— and the first version of this section then called it "inert." Neither holds. Fired with
the trigger it was actually optimized to produce, **the reconstruction is retrieved into the
top 3 for 100.0% of 300 diverse, unrelated real queries, while sitting at 0.0% without it
and 0.0% under a different attack's trigger.** That is not a weak attack or an inert one; it
is a near-perfect retrieval backdoor with clean trigger specificity, and the benign floor
stays at ~0.5% in the same condition, so it is a real signal and not an artifact of adding
tokens to queries.

**The reviewer's premise for this item — "it's the least retrievable of the 7 families, so
every AgentPoison defense number is measured against an attack that barely works" — is
therefore not correct, and neither was this project's own supporting measurement.** A
backdoor that is invisible on ordinary queries is working as designed; "low top-3 rate on
plain queries" was never evidence of weakness.

**The real, remaining caveat is different and narrower, and Phase 4 already disclosed it:**
the reconstruction reaches 100% because the optimized trigger tokens are embedded as
*visible text inside the poison record itself* (`trigger_run.py`'s docstring states this
plainly: proximity is guaranteed "by shared tokens (not by a second gradient
optimization)"), so the retrieval win is substantially by construction. The paper's
passage-side optimization is not ported. The published material, which does not take that
shortcut, reaches 36.2% on its own trigger. So the honest ordering is: the reconstruction
demonstrates the backdoor *effect* reliably but by an easier mechanism than the paper's, and
the published material demonstrates it at a lower but still large rate by the authors' own
construction.

Detection, by source:

| Config | Published AgentPoison (6) | Published MINJA (21) | Reconstruction (1) |
|---|---|---|---|
| B9 | 0/6 | 0/21 | 0/1 |
| B11 | 4/6 | 9/21 | 0/1 |
| B12 | 2/6 | 11/21 | 0/1 |
| B13 | **4/6** | **11/21** | 0/1 |

**A genuine weakness this exposes, stated plainly:** every config excludes the
reconstruction 0/1, and B12 excludes only 2/6 of the published AgentPoison records. The
attack works (100% trigger retrieval) and the content-level defenses largely do not catch
it — the poison text reads as an ordinary address-update note plus a nonsense token run.
B13 recovers 4/6 on the published material but still misses the reconstruction. This is now
a *defense* gap backed by a *working* attack, which is a more useful finding than the
previous "the attack doesn't work, so the numbers don't mean much."

**Consequence for headline claims:** the reason AgentPoison was being dropped from headline
claims was attack weakness, and that reason does not survive this measurement. AgentPoison
retrieval-side numbers are restored to ordinary standing, carrying the construction caveat
above; the `n=1` reconstruction record remains far too small a population for any rate
claim on its own.

## 8c. Two "leave it as an honest limit" items, checked rather than assumed

The reviewer listed several findings as better left as disclosed limits. Two of them make
claims that its own data can confirm or refute, so they were checked rather than restated.

**B10's learned GNN contributes exactly nothing in the shipped configuration — confirmed,
and the decision is now recorded.** `b10_ablation_results.json` runs the blend weight at
W=0 (no learned component), W=0.25 (shipped) and W=1 (learned only), gated and ungated:

| Variant | in-sample 15 | regen 9 | evasion 47 | frozen75 34 | benign FPR (502) |
|---|---|---|---|---|---|
| gated, W=0 / W=0.25 / W=1 | 14/15 | 4/9 | 11/47 | 16/34 | 0/502 |
| ungated, W=1 (GNN only) | 1/15 | 0/9 | 0/47 | **33/34** | **18/502** |

**Every gated variant is byte-identical across all three weights** (`only_a = only_b = 0`,
p=1.0 on every population): the gate decides everything and the learned score changes no
decision at all. The one place the learned component does something real is *ungated* on
`frozen75`, the arena that contains coordinated near-duplicate poison pools — 33/34 versus
16/34 — and it pays for that with a 3.6% benign false-positive rate and near-total loss of
isolated-poison detection (0/47 on evasion variants). **Decision: B10 is retired from the
shipped stack and kept only as a documented ungated variant for coordinated attacks**,
which is exactly what the reviewer proposed, now with the ablation numbers attached.

**Multi-hop 27/60 really is the model's reasoning ceiling, not a retrieval or defense
problem — and a stronger agent does not move it.** `multihop_scored.json` already contains
the controlled comparison, including an oracle condition that hands the agent exactly the
gold evidence turns:

| Condition | llama2 | qwen2.5:7b |
|---|---|---|
| single-shot retrieval | 27/60 | 28/60 |
| query decomposition | 28/60 | 25/60 |
| **oracle (gold evidence supplied)** | **36/60** | **32/60** |

Perfect retrieval buys roughly 9 questions and still tops out near 60%, and the stronger
model is not better (32 vs 36 at the ceiling). So this is genuinely a reasoning limit of
7B-class local models, and the "use a stronger agent" remedy does not apply to it — worth
knowing, because that remedy *is* being applied to Track A utility (§10), where the task is
single-hop factual recall and the headroom argument does hold.

## 9. What this round did NOT fix

- **AgentPoison's trigger was not re-optimized** (§8b explains what was done instead, and
  why the resulting evidence is stronger than a re-optimization would have been for the
  question the reviewer was actually asking). The reconstruction stays excluded from
  headline claims.
- **Human-written attacks.** Still none. The 266 externally-authored attacks
  (`external_attacks.py`) narrow the authorship confound — they were written by the MINJA,
  AgentPoison, InjecAgent, BIPIA and AgentDojo authors, not by this project or its models —
  but InjecAgent and BIPIA document LLM assistance in building their own datasets, so
  "not authored by this project" is the honest claim, not "human-written".
- **A LICENSE.** Still absent, still a decision for the project owner; the repository
  remains all-rights-reserved by default, so nobody can legally reuse it.
- **Track A's weak agent.** The harm study (§7) now uses `qwen2.5:7b` with an independent
  `llama3.1:8b` judge, but the Track A utility campaign itself still runs on `llama2`
  (122/300). Its "no utility cost" numbers keep that caveat.
