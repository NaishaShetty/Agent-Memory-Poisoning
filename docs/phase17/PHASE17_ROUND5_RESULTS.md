# Phase 17 — external review round 5 (2026-09-30)

Round 4 ended with the finding that made this round necessary: measured against published
detectors, **B12's advantage is 2.80x on attacks this project wrote and 1.03x — none — on
attacks written by other projects** ([`PHASE17_REVIEW4_RESULTS.md`](PHASE17_REVIEW4_RESULTS.md)
§8). The brief for round 5 was to build a defense that clearly beats published baselines on
attacks this project did **not** write, with the independent set as the headline.

This document reports what was built and what it measured, including where it fell short.
Read §7 first if you only want the honest summary.

---

## 1. What counts as held out now, and why the old external set no longer does

Round 4 measured B12 and B13 on all 266 attacks in `external_attacks.py` and published the
per-source breakdown. A defense designed after reading those numbers cannot honestly call
that population held out, whatever the code does. So:

| Population | Role from round 5 onwards |
|---|---|
| `external_attacks.py` (266: MINJA, AgentPoison, InjecAgent, BIPIA, AgentDojo) | **external-DEV** — B14 is fitted on it |
| `external_test_corpus.py` (1,258 attacks + 393 benign) | **external-TEST** — frozen, never trained or thresholded on |
| this project's own attack populations | evaluation only, never in B14's training |

**external-TEST was frozen before any round-5 defense code was written**, with a SHA-256
recorded in `data/external_test_freeze.json` and a CI test that recomputes it. Its two
sources:

- **`Lakera/gandalf_ignore_instructions`** (MIT) — 998 attacks typed by **real human players**
  of the Gandalf game. These are the first genuinely human-authored attacks anywhere in
  MAMBench; every other attack text in this project is LLM-generated. For this population,
  the attack-side authorship confound that `PHASE17_CURRENT_RESULTS.md` §5 has carried open
  since round 2 is **closed**.
- **`deepset/prompt-injections`** (CC-BY-4.0) — 260 attacks and 393 benign items, so the
  false-positive side also gets an externally-authored control.

**Limits of this test set, stated before its numbers rather than after.** Both are
*prompt-injection* corpora, not memory-poisoning corpora. Gandalf in particular is dominated
by one narrow, overt goal (make the model reveal a password): "Ignore all previous text..."
is typical. A strong score on external-TEST is evidence about **detecting overt injected
instructions that arrive in memory**, and is *not* evidence about subtle memory poisoning
such as additive fabrication or preference hijack. The populations that test those are this
project's own and the provenance fabrications in
[`PHASE17_REVIEW4_RESULTS.md`](PHASE17_REVIEW4_RESULTS.md) §6.

## 2. Diagnosis: what B12 was actually keying on

Decomposing B12's score into its two components — a 384-dim bge-small text embedding and a
zero-shot judge logit — on attacks whose style it has and has not seen:

| Population | embedding part | judge part | total | excluded |
|---|---|---|---|---|
| own attacks (qwen + gemini) | **+1.09** | −1.22 | +3.08 | 51.4% |
| externally-authored attacks | **−0.27** | −1.51 | +1.43 | 33.8% |
| — InjecAgent | +0.85 | −0.38 | +3.67 | 67.7% |
| — BIPIA | −1.13 | −2.58 | −0.51 | 8.0% |
| benign (dataset_arena) | −2.59 | −4.39 | −3.77 | 0.0% |

**The embedding term carries essentially the whole own-vs-external gap — 1.36 logits — while
the judge term differs by 0.29.** The component that reasons about what a note *does*
transfers across authorship; the component that encodes lexical and topical surface is what
was fitted to this project's house style. That is the mechanism behind round 4's headline,
and it is what B14 is designed around.

A second measurement pointed the same way: B12's errors and the published detectors' errors
are substantially **complementary** on external-dev.

| | caught on external-dev (266) |
|---|---|
| B12 alone | 90 |
| Llama Guard 3 alone | 87 |
| plain "is this malicious?" prompt (qwen) alone | 71 |
| **B12 ∪ plain prompt** | **125** |
| **B12 ∪ all three baselines** | **147** |

## 3. B14 — the round-5 defense

`phase17/b14_live.py`. B12 and B13 are both left unchanged, so their published numbers stay
valid.

1. **The raw text embedding is removed** — directly from §2's diagnosis — and replaced by a
   calibrated fusion over eleven signals that each describe a note's intent or effect: this
   project's zero-shot judge, **three published detectors** (Llama Guard 3, ProtectAI
   deberta-v3 prompt-injection v2, a GPT-2 perplexity filter), plain "is this malicious?"
   prompts on **two** model families, the steer/lineage/worm judge tiers, and two cheap
   lexical priors.
2. **Everything structural from B13 is kept**: source-aware trust, NLI corroboration of
   unsupported personal claims, the unsupported-preference rule, and the carry-forward write
   guard. These are style-independent by construction, which is why they survived round 4.
3. **Fitted on dev only** (`train_b14.py`): the designated dev pool, external-DEV, and
   AgentDojo's dev benign half (so the model cannot learn "not a user turn ⇒ attack").
   Thresholds from group-held-out out-of-fold scores at 0.5%/2% FPR on dev negatives — the
   same protocol B12 used.

B14 refuses to score at all if its fitted model file is absent, rather than falling back to
uncalibrated weights, since that would silently be a different defense.

**Including published detectors inside B14 means "B14 beats Llama Guard 3" is partly a
superset relation, not a fair fight.** The number that carries real information is B14's
gain over its own best single component, and that is reported alongside.

## 3b. The attack register — what this benchmark actually contains

Round 5 kept discovering attack populations by accident: that `memory_worm` never implemented
its own mechanism, that `sleeper` was being measured in its dormant condition, that the seven
founding families have 24 records between them, that several BIPIA items are not attacks under
any threat model. Each surfaced while looking at something else. `phase17/attack_register.py`
now enumerates every population, with who authored it, whether its instances were ever checked
against their own documented mechanism, and whether it has ever been run end-to-end against an
undefended agent.

**14 populations, 2,120 attack instances, 20 recorded gaps.** Two findings worth stating
plainly:

- **`corpus_extended` (138 instances) and `frozen75_corpus` (34) appear in no round-4 or
  round-5 evaluation table at all.** They were being carried but not reported. `frozen75`
  matters particularly: it is the only arena containing coordinated near-duplicate clusters,
  which is what the B10/coordination work depends on.
- **Only 2 of 14 populations have ever had their instances validated against their own
  mechanism** (`memory_worm_regen`, `founding_regen`). That is the exact defect that made
  every prior `memory_worm` number meaningless, and it is unmeasured everywhere else.

The register prints its own gap list, so an unmeasured attack set is a visible row rather than
an omission. The validity audit now covers all 14.

## 3c. The seven founding families were too small to evaluate

`agentpoison` 2, `memorygraft` 2, `sleeper` 2, `dsrm` 4, `farma` 4, `mpbench` 4, `minja` 6 —
24 records in total. At that size the n=203 harm study's `farma` 0/4 and `mpbench` 0/4 cannot
be distinguished from having asked the wrong question four times, which, given that the same
study's `authority_impersonation` 0/15 turned out to be exactly that, is the likelier reading.

`phase17/founding_family_regen.py` enlarges each family using the pattern that worked for
`memory_worm`: the required structure is stated explicitly in the prompt, and **every instance
is validated against a judge before being accepted**, with failures retried. The generator is
`mistral:7b` and the validator `llama3.1:8b` — deliberately neither is qwen2.5, since adding
200 more qwen-authored attacks would deepen the very confound §2 measures. They remain
LLM-authored, and they are more instances of this project's *reconstructions*, not of the
published attacks.

**Result: 208 of 210 accepted**, i.e. 208 instances that each satisfy their own family's
mechanism check. The founding families go from 24 records between them to 232:

| Family | before | after |
|---|---|---|
| dsrm | 4 | **34** |
| farma | 4 | **34** |
| mpbench | 4 | **34** |
| minja | 6 | **35** |
| memorygraft | 2 | **32** |
| sleeper_memory_poisoning | 2 | **32** |
| agentpoison | 2 | **31** |

Per-family harm and detection are measurable for the first time. The two rejected instances
are recorded as invalid rather than dropped, so the acceptance rate stays visible.

## 4. Attack validity: are these attacks even working?

*(filled in from `phase17/attack_validity_audit.py`, whose criterion was committed before it
ran: an attack counts as working only if the undefended agent complied with the note AND did
not comply on the same task with the note absent. It never consults any defense's decision.)*

## 5. The round-5 comparison

### 5a. Leave-one-source-out (available now)

Each external source scored by a model **refit with that source entirely removed** — the
honest estimate for a source the model has never seen. B12 and B13 are shown for reference;
neither was fitted on external-dev at all, so their numbers are already out-of-sample here.

| Source | B12 | B13 | **B14 (LOSO)** |
|---|---|---|---|
| AgentDojo (27) | 23 | 23 | **26** |
| AgentPoison (6) | 2 | 4 | **5** |
| BIPIA (150) | 12 | 20 | **23** |
| InjecAgent (62) | 42 | 42 | 41 |
| MINJA (21) | 11 | 11 | **14** |
| **Total** | 90/266 (33.8%) | 100/266 (37.6%) | **109/266 (41.0%)** |

B14 improves on 4 of 5 sources and loses 1 on InjecAgent. The AgentPoison gain (2 → 5) is
attributable to the perplexity feature: that attack's trigger is a nonsense token run, which
a fluency model detects and a semantic judge does not.

### 5b. What B14's fitted coefficients say it relies on

| feature | weight | | feature | weight |
|---|---|---|---|---|
| perplexity | −4.70 | | judge_concept | +1.38 |
| llama_guard3 | +2.19 | | steer | +1.15 |
| prompt_llama31 | +2.06 | | lineage | +0.86 |
| deberta_pi | +1.93 | | len_z | +0.16 |
| prompt_qwen | +1.49 | | worm | −0.15 |
| imperative | +1.46 | | | |

(The perplexity column is sign-flipped at construction, so a large negative weight means
*high* perplexity counts as suspicious — which is what catches nonsense triggers.)

**This exposed a bug that reading the coefficients caught.** `worm` (−0.15) and `lineage`
(+0.86) were being diluted inside the fusion because the dev pool contains very few positives
of either, yet both are zero-false-positive detectors standing alone (worm: 29/29 corrected
self-replicating notes at 0/1125 benign). Folding them into a learned average threw away
precision B13 already had. They are hard rules again in B14, and remain features as well.

### 5c. The headline external-TEST comparison

Run once on the frozen corpus (1,258 attacks, **998 of them typed by real humans**), which no
config or baseline was fitted or thresholded on. Recall is exclusion rate; FPR is over all
1,552 benign items.

| System | Recall | FPR | paired vs B14 |
|---|---|---|---|
| **B14** | **90.8%** [89.1, 92.3] | 0.84% | — |
| llm_prompt_qwen @oracle | 86.5% | 0.52% | p=3.5×10⁻⁶ |
| deberta_pi_v2 @dev | 85.4% | 0.64% | p=6.5×10⁻¹⁰ |
| deberta_pi_v2 @oracle | 84.6% | **0.13%** | p=4.7×10⁻¹² |
| llm_prompt_qwen @dev | 77.9% | 0.06% | p=2.5×10⁻³⁴ |
| B13 | 71.5% | 0.39% | p=8.7×10⁻⁷² |
| B12 | 66.2% | 0.39% | p=1.5×10⁻⁹¹ |
| llama_guard3 @dev | 32.0% | 2.00% | p=1.1×10⁻²⁰⁶ |
| B9 (pre-round-4 live rule) | 0.0% | 0.00% | — |

**B14 beats every baseline on recall, including at oracle thresholds chosen on test data in
the baselines' favour, every comparison significant. It beats B12 by +24.6 points.** The
fusion generalized to 998 attacks written by people, which is the question round 4 left open.

**It is still not "clearly and substantially better", and three facts say why.**

1. **This is a recall/FPR trade, not dominance.** `deberta_pi_v2 @oracle` reaches 84.6% at
   **0.13% FPR**; B14 buys +6.2 points of recall at 6× the false-positive rate. Which is
   preferable is a deployment decision, not a benchmark verdict.
2. **The honest gain is +5.4 points, not +24.6.** `deberta_pi_v2` is a *component of B14*, so
   "B14 beats the deberta classifier" is partly a superset relation — exactly as §7's
   self-review predicted. B14's gain over its own best single component is **+5.4 points**,
   and that is the number that is not circular.
3. **A single off-the-shelf classifier gets 85% here for one local forward pass.** That is a
   strong, cheap baseline this project should have been measuring against years of phases
   ago, and it reframes what the in-house stack was ever worth on this class of attack.

### 5d. Cost — the finding that most limits B14

Cold cache, sequential, one memory per pool (`phase17/defense_cost.py`):

| Config | seconds per memory | relative to B12 |
|---|---|---|
| B13 | 0.13 | **0.81×** |
| B12 | 0.16 | 1.00× |
| B9 | 0.27 | 1.69× |
| **B14** | **28.73** | **179×** |

**B14 costs 179× B12 per admitted memory.** It issues roughly seven model calls (Llama Guard,
two plain-prompt judges, three judge tiers, a concept score) where B12 issues an embedding and
one judge, and on a single-GPU host each model switch is a reload. Memory admission is not a
per-token path — it happens when a memory is written, not on every turn — so ~29s may be
tolerable in some deployments and is plainly not in others. But a +5.4 point recall gain over
a single deberta forward pass, at 179× the cost, is a trade that must be stated wherever the
recall number is.

**B13 is cheaper than B12** (0.81×) while scoring higher on every population, which makes it
the better default of the two.

### 5d-bis. What corroboration is worth when the conversation IS available

`eval_round5` supplies provenance but no conversation evidence, so every B13/B14 number in it
is a floor with the corroboration signal switched off. For Track B and the `evasion_47`
rewrites of it, the real LoCoMo conversation exists and a deployment would have it
(`phase17/evidence_available_check.py`):

| Population | B12 | B13 (no evidence → with) | B14 (no evidence → with) |
|---|---|---|---|
| trackb_original_15 | 9 → 9 | 9 → **11** | 10 → 10 |
| trackb_regen_9 | 3 → 3 | 3 → **4** | 4 → **5** |
| **evasion_47** | 4 → 4 | **4 → 28** (p=1.2×10⁻⁷) | 4 → **11** (p=0.016) |

**`evasion_47` is the headline here.** Defense-aware rewrites have sat at 3–4/47 for every
configuration since round 3, and this project has repeatedly concluded that content-only
detection had hit its ceiling on them. That conclusion was right about the ceiling and wrong
about why: the limit was looking only at the text. **B13 reaches 28/47 (59.6%) once the real
conversation is available**, because a paraphrase of a fabricated claim is still unsupported
by what the user actually said — rewording changes the text, not the evidence.

Two qualifications, both load-bearing:
- **This applies only where the conversation exists.** Track B's poisons were injected into a
  specific real LoCoMo conversation; the invented-persona populations have nothing to check a
  claim against, and get no benefit. It is not a general +51-point gain.
- **B14 gains far less than B13 here (11 vs 28)**, because B14's two-signal rule requires a
  claim to be unsupported *and* independently behaviour-changing before excluding it. That
  rule was added to fix B13's 1.1% benign-exclusion cost (§6 of the round-4 results), and on
  this population it suppresses most of what B13 catches. **That is a real regression
  introduced by a fix**, it is visible only because both configs were kept, and the right
  resolution is a dev-side revisit rather than picking whichever number flatters.

### 5e. Legitimate standing instructions — provenance decides the answer

The reviewer's own example, "always CC my wife on invoices". 40 such instructions:

| Config | no provenance recorded | provenance says `user_turn` |
|---|---|---|
| B12 | 2 excluded, **14 flagged (35%)** | 2 excluded, 14 flagged (B12 ignores provenance) |
| B13 | 2 excluded, 14 flagged | **0 excluded, 2 flagged (5%)** |
| B14 | **4 excluded**, 14 flagged | **0 excluded, 4 flagged (10%)** |
| deberta / prompt baselines | 0 excluded, 0 flagged | 0 excluded, 0 flagged |

**With provenance recorded, B13 and B14 fix the cost round 4 flagged**: the 35% flag rate
falls to 5–10% and hard exclusions go to zero. Without it, B14 is *worse* than B12 (4 vs 2
exclusions) — the `imperative` feature (+1.46) does exactly what §7 warned it would, since a
standing instruction is imperative by definition.

So the structural claim this project has been making — that recording where a memory came from
is the highest-value change available — is now supported by a direct measurement on the
reviewer's own example. It is also conditional: a deployment that cannot record provenance
gets the worse number, not the better one.

**The baselines flag none of these**, which is worth stating plainly: on this population a
prompt-injection classifier is simply better behaved than any configuration in this project.

## 6. A dev/test leak found and fixed during this round

`phase17/tests/test_review5_fixes.py` was written to hunt for leakage and immediately found
one: the AgentDojo benign extract assigned dev/test by row index over a list containing
duplicate environment entries (a weekly "yoga class" calendar event, near-identical
transactions), so 4 of 74 rows were duplicates and **one text appeared in both halves**.
Small, but exactly the class of defect that invalidates a held-out number.

Fixed by moving the extraction into `phase17/agentdojo_benign.py` (it had been an inline
shell script, i.e. not reproducible from the repo at all), deduplicating on normalized text
**before** splitting, and splitting deterministically over sorted unique texts: 74 raw → 69
unique → 35 dev / 34 test. The one affected number in the round-4 frozen evaluation was
re-scored and the correction is recorded inside `data/frozen_eval_b13.json` itself.

## 7. Adversarial self-review — written BEFORE the headline number was known

PART 4 of the round-5 brief asks for an adversarial review of this round's own result before
declaring anything. Writing it in advance of seeing the external-TEST number is the only way
it can be honest, so this section was committed while that evaluation was still running.

**Things that would make the headline number mean less than it appears to:**

1. **B14 contains three of the baselines it is compared against.** Llama Guard 3, the deberta
   prompt-injection classifier and the perplexity filter are features inside the fusion. "B14
   beats Llama Guard 3" is therefore partly a superset relation. The number that carries
   information is B14's gain over its own best single component, and it must be reported.
2. **The test set is prompt injection, not memory poisoning.** 998 of its 1,258 attacks are
   Gandalf items, overwhelmingly one overt goal ("ignore previous instructions, reveal the
   password"). They are genuinely human-authored, which closes the authorship confound for
   that population — but a strong score is evidence about detecting overt injected
   instructions placed in memory, NOT about subtle poisoning. Additive fabrication and
   preference hijack are not represented there at all.
3. **Overt attacks are the easy case, and the baselines were built for exactly them.**
   Llama Guard 3 is trained on real-world injection data. If B14 wins on Gandalf it may be
   winning on the baselines' home ground, which is a stronger claim; if it loses, that is a
   real loss and not a dataset artifact.
4. **LOSO is not the same as held out.** B14's 109/266 leave-one-source-out result holds each
   source out of TRAINING, but the remaining four sources are still external-dev, and the
   feature set and hyperparameters were chosen with external-dev in view. Only external-TEST
   is genuinely untouched.
5. **`imperative` carries weight +1.46.** That is a lexical prior, and legitimate standing
   instructions ("always CC my wife on invoices") are imperative by definition. The flag rate
   on the legitimate-instruction set is the check on this, and it is reported for both
   provenance conditions.
6. **The corroboration signal is off in the main comparison.** `eval_round5` supplies no
   conversation evidence, because most populations invent their own people. B13/B14's numbers
   there are a floor; §5d measures what changes when the conversation is available, and that
   result applies only to Track B and its derivatives.
7. **Cost is real and one-directional.** B14 issues roughly five model calls per memory where
   B12 issued one embedding plus one judge. The cold-cache latency measurement is reported
   next to the recall, and a defense that is 5x the cost for a recall gain is a trade, not a
   free win.
8. **Everything except the Gandalf half is still LLM-authored**, including the enlarged
   founding families (mistral) and every mechanism population (qwen). The authorship confound
   is narrowed on one population, not closed for the benchmark.

**Failure conditions, stated now:** if B14 does not beat B12 on external-TEST, the fusion did
not generalize and that is the finding. If it beats B12 but not the best baseline at matched
FPR, then the honest claim is "competitive with published detectors, with a lower
false-positive rate", not "clearly better". Neither will be reframed.

## 8. Honest summary

*(filled in last, after §5)*
