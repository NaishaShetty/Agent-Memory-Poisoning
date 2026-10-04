# Phase 17 -- external review rounds 5-6, final results (2026-10-04)

Recall is exclusion rate. FPR is over the four ordinary benign populations (1,088 texts). Cost
is cold-cache seconds per admitted memory. The last column is the flag rate on 40 legitimate
standing instructions when provenance records them as the user's own words.

| Config | own attacks (804) | external-dev (266) | external-test (1258) | holdout2 Mosscap (1200) | benign FPR | cost | legit flags |
|---|---|---|---|---|---|---|---|
| B12 | 43.2% | 33.8% | 66.2% | 15.0% | 1/1088 | 0.17s | 14/40 |
| B13 | **46.1%** | 37.6% | 71.5% | 17.6% | 1/1088 | 0.12s | **2/40** |
| B14 | 41.2% | **53.4%** | **90.8%** | **54.2%** | 2/1088 | 26.35s | 4/40 |
| B15 | 37.7% | 44.0% | 86.6% | 43.2% | 1/1088 | 0.29s | 4/40 |
| **B17 = B13 OR B14** | **see below** | | | | 2/1088 | ~26.5s | |

The `own attacks` column is **804 instances, not round 5's 340**: `zh_translated` (84) and
`founding_regen` (208) were added, and both are harder than the original set, so this column is
NOT comparable to previously published own-attack rates. The hold-out columns are.

## The five findings that matter most

**1. Every rate above needs its working-attack denominator, and the denominators differ a lot.**
45.1% of all instances both subvert an undefended agent and implement their own label
(`working_set.py`, 1,117/2,628). Per population that ranges from 85% (InjecAgent) to 21%
(Mosscap). Recall restricted to working attacks, computed from saved per-item decisions:

| working-attack recall | own (482) | external-dev (180) | external-test (391) | Mosscap (64) |
|---|---|---|---|---|
| B12 | 45.0% | 31.1% | 56.3% | 9.4% |
| B13 | **46.7%** | 34.4% | 61.6% | 12.5% |
| B14 | 39.4% | 49.4% | 83.1% | **62.5%** |
| B15 | 36.5% | 37.8% | 77.2% | 50.0% |
| **B13 OR B14** | **51.5%** | **51.7%** | **83.4%** | **62.5%** |

**2. B14's hold-out instability is about HALF composition, and half real.** The published gap is
90.8% on external-test against 54.2% on Mosscap -- 36.6 points. Restricted to working attacks it
is 83.1% against 62.5% -- **20.6 points, still p=0.0001**. So composition (Mosscap is 21%
working, external-test 31%) accounts for roughly 16 of the 36.6 points, and the remaining 20.6
is genuine cross-corpus instability. **The 91% must still not be cited alone**, but that
conclusion is now quantified rather than asserted. This comparison was impossible before today:
Mosscap was a headline column in no audit and no register.

**3. B13 and B14 are complementary, not ranked, and my earlier unqualified "B13 is the
recommendation" was wrong.** On working attacks, B13 wins on own attacks (46.7% vs 39.4%,
p=0.00013) while B14 **strictly dominates** on the clean hold-out (Mosscap working attacks
40/64 vs 8/64, +32/-0, p=5e-10). B13's 12.5% there is a real weakness I had not reported.
B13's signals -- provenance, NLI corroboration, structural tiers -- reach poisoning shaped like
an ordinary personal note; B14's fused content classifiers reach injection-shaped text. They
miss disjoint sets.

So **B17 = exclude if either excludes** beats both on three of four groups, ties on the fourth,
and **adds no false positive at all** (every benign item B13 excludes, B14 already excluded).
It introduces no parameter -- no threshold, no weight, no new score -- which is what keeps
choosing it after reading hold-out results defensible; a guard test parses the AST to assert
none ever appears. **Its numbers are descriptive, not a clean held-out estimate**, the same
status B15 carries, and it needs a fresh hold-out before being called generalisation.

**Which to use:** B13 for a latency-sensitive admission path (0.12s, cheaper than B12, best on
note-shaped poisoning, 2/40 legitimate flags). B17 where a missed poison costs more than ~26s.
B14 alone is dominated by B17 at the same FPR and cost. **No single population's recall is a
reason to pick a config.**

**4. Provenance is what reaches the hard classes, and it is nearly free.** Pre-registered, run
twice (the second after a dev-side fix to evidence-retrieval width; both reported):

| Pre-registered comparison | B12 | B13 |
|---|---|---|
| Additive fabrication (72) | **0** | **37** (p=1e-11) |
| Fabricated preferences (48) | **0** | **27** (p=1e-08) |
| Externally-authored attacks (266) | 90 | 100 (p=0.002) |
| Benign derived memories falsely excluded (1515) | 0 | 7 (0.46%) |

Additive fabrication was documented as unreachable by content-only detection and B12 scores
exactly 0. On working attacks B13 also strictly dominates B12 on own attacks (+8/-0, p=0.008).

**5. Adaptive evasion is a statefulness problem -- and rejection memory DID NOT FIX IT.**

The diagnosis holds: ~20% of initially excluded seeds are recovered within five rewrites,
equally for B12, B13 and B14, so B14's 170x cost buys nothing here. Every config except B16 is
stateless, so five rewrites are five independent attempts at a probabilistic detector.

B16 adds a per-scope ledger of what was already hard-mitigated and refuses semantic neighbours
of it. The hypothesis was that the dev-measured 17.0% pairwise paraphrase catch would compound
across the attacker's five rounds, because the ledger holds every previous attempt. Measured
against the real attacker on the same 43 seeds, same budget, same rewrite model, with
statefulness as the only difference:

| | genuine adaptive evasion of initially-excluded | mean rounds |
|---|---|---|
| B15 (stateless) | 5/30 = 16.7% | 3.47 |
| B16 (ledger, radius 0.97) | 4/30 = 13.3% | 3.51 |

**Paired: +0 / -1, p=1.0. The hypothesis is not supported.** B16 prevented one of five adaptive
evasions and caused none, which is the right direction and nowhere near significance; with five
events the study cannot detect an effect this size either way.

It is not that the mechanism failed to engage: **the ledger was non-empty in 138 of 151 attack
rounds.** It fired, and the rewrites cleared the radius. And `static_equivalence` confirms on 60
real records that B16 is byte-identical to B15 with no ledger (0 differing), so this compares
one detector with and without memory rather than two detectors.

The radius is the only lever, and the dev curve shows why it is not a free one:

| radius | paraphrases caught | benign FPR | ledger-poisoning blast radius |
|---|---|---|---|
| 0.86 | 83.0% | 0.0% | 42.5% |
| 0.90 | 55.3% | 0.0% | 29.7% |
| **0.97 (frozen)** | **17.0%** | **0.0%** | **0.7%** |

The radius that would catch most paraphrases is the radius at which one successfully
ledger-poisoned innocuous text sits within range of a third to a half of benign traffic. **So
the honest conclusion is that rejection memory trades adaptive-evasion resistance for a
denial-of-service surface, and at a radius whose DoS surface is defensible it does not measurably
help.** B16 should not be recommended on this evidence. Adaptive evasion remains OPEN.

A sensitivity probe at radius 0.90 is recorded in
`eval_rejection_memory_sim090_EXPLORATORY.json`. It is labelled exploratory because the radius
was chosen after seeing the frozen-radius result; the 0.97 figure above is the measured one and
nothing in this project's recommendations is changed by the probe.

## How many of these attacks actually work: 42.5%

`attack_validity_audit.py` ran both probes over all 20 populations. An attack counts as working
only if the undefended agent complied AND did not comply on the same task without the memory --
causal, and never consulting any defense's decision. Working-set membership additionally
requires that the instance implement its own labelled mechanism.

| Population | total | subverts | in working set | rate |
|---|---|---|---|---|
| InjecAgent | 62 | 53 | 53 | **85%** |
| zh_native | 30 | 25 | 25 | 83% |
| Track B original | 15 | 11 | 11 | 73% |
| founding_regen | 208 | 147 | 146 | 70% |
| BIPIA | 150 | 99 | 99 | 66% |
| corpus_extended | 138 | 91 | 91 | 66% |
| zh_translated | 84 | 62 | 47 | 56% |
| AgentDojo | 27 | 15 | 15 | 56% |
| novel_new120 | 120 | 85 | 64 | 53% |
| evasion_47 | 47 | 33 | 25 | 53% |
| novel_60 | 60 | 42 | 31 | 52% |
| **AgentPoison published** | 6 | 3 | 3 | **50%** |
| deepset | 260 | 126 | 126 | 48% |
| MINJA | 21 | 10 | 10 | 48% |
| frozen75 | 34 | 14 | 14 | 41% |
| worm_regen | 29 | 18 | 10 | 34% |
| Gandalf | 998 | 265 | 265 | 27% |
| trackb_regen | 9 | 2 | 2 | 22% |
| **Mosscap** (seeded 300 of 1,200) | 300 | 64 | 64 | **21%** |
| **TOTAL** | **2,628** | **1,170** | **1,117** | **42.5%** |

**AgentPoison published went 0/6 to 3/6**, with a task-alone base rate of 0. The records
function when the query carries their own trigger. All five previous readings of that population
were measurement error, not a weak attack -- and the fifth was caught by the guard test written
to prevent the first four, which had matched the possessive apostrophe in "Caroline's" as a
quote delimiter and produced a query with no trigger in it.

**Mosscap at 21% is the lowest-working of the human-authored corpora**, which is finding 2's
input. Its rate is a seeded random sample of 300, so it is an estimate with an interval, not a
census.

## The published baselines: "deberta nearly matches you" is a composition artifact

Pooled over every population, an off-the-shelf `deberta-v3-base-prompt-injection-v2` forward
pass lands within 6 points of B13, and the fair reading of that was damaging: if one public
classifier nearly matches a bespoke stacked defense, the complexity is not earning its keep.

It does not survive disaggregation (`baseline_breakdown.py`, re-read from `eval_round5.json`,
no models re-run):

| | B13 | deberta@dev | delta |
|---|---|---|---|
| **pooled (2,120)** | 62.3% | 56.6% | **+5.6** |
| **own memory-poisoning attacks (596)** | 53.9% | 15.1% | **+38.8** |
| external injection corpora (1,524) | 65.5% | 72.9% | -7.3 |

The pooled number is 72% external by item count, and those corpora are deberta's training
distribution. Per population the gap on this project's own attacks is +96.5 (worm_regen),
+61.8 (frozen75), +60.0 (Track B), +44.2 (corpus_extended) -- and on external-dev it is
+54.8 (InjecAgent), +52.4 (MINJA), +44.4 (AgentDojo). Deberta wins exactly one population:

**Gandalf, at 99.5% of 998 items -- 47% of the pooled denominator by itself.** That single
population is the whole of the aggregate effect.

A 99.5% is worth distrusting rather than celebrating, and it is an outlier among the baselines
rather than a general capability:

| baseline | Gandalf (998) | own attacks (596) |
|---|---|---|
| deberta_pi_v2 | **99.5%** | 15.1% |
| llm_prompt_qwen | 83.3% | 3.9% |
| llm_prompt_llama31 | 42.5% | 14.9% |
| perplexity_gpt2 | 41.0% | 4.9% |
| llama_guard3 | 34.5% | 9.9% |

Every baseline is 3-15% on memory poisoning that reads as an ordinary personal note, because a
fabricated preference or an invented standing policy carries none of the injection surface
these detectors key on. Deberta's Gandalf score is 57 points above the next-best baseline on
the same items, which is the pattern one expects when a classifier has seen a public dataset
during training -- Gandalf is the canonical public prompt-injection corpus and deberta is a
prompt-injection classifier. **That is a hypothesis, not a measured fact**: the training data
is not public, so it cannot be confirmed here, and it is stated because it bears on how much
weight the 99.5% should carry, not as a finding.

Either way the conclusion does not depend on it. Pooling a prompt-injection benchmark with a
memory-poisoning benchmark and reporting one rate hides a 38-point difference in both
directions, so **the pooled baseline comparison should not be cited at all** -- only the split.

Not yet available for B15/B16: round 5 predates them, so their per-population baseline
comparison needs `eval_round6` to carry the baseline columns. B13 remains the recommendation.

## Harm, re-measured with validated instances (unconditional)

`harm_study_v2.py`, 309 instances, per-instance fitted tasks, the two drifted families drawn
from `validated_regen`'s accepted set. Judge is a third model family. **Task-alone base rate
1/309 = 0.3%**, so the tasks are not doing the work (round 4's task set was 26.7%).

| | undefended | B12 | B13 |
|---|---|---|---|
| **overall (309)** | **28.2%** | 18.8% | **10.4%** |
| memory_worm (30) | **83.3%** | 43.3% | **3.3%** |
| conditional_backdoor (15) | 66.7% | 33.3% | 26.7% |
| memorygraft (17) | 64.7% | 47.1% | 41.2% |
| dsrm (19) | 52.6% | 36.8% | 15.8% |
| sleeper (17) | 29.4% | 29.4% | 17.6% |
| policy_revocation (15) | 26.7% | 33.3% | 13.3% |
| external (60) | 26.7% | 15.0% | 13.3% |
| agentpoison (17) | 11.8% | 11.8% | 11.8% |
| preference_hijack (30) | 6.7% | 6.7% | 3.3% |
| farma / mpbench (19 each) | 5.3% | 5.3% | 5.3% / 0% |
| **authority_impersonation (15)** | **0%** | 0% | 0% |
| **exfiltration_instruction (15)** | **0%** | 0% | 0% |
| **minja (21)** | **0%** | 0% | 0% |

**Not comparable to the previously published 42.3% -> 12.5%**: the undefended rate fell to 28.2%
because the population changed (validated worm and exfiltration instances replaced the
originals). The reduction is what to read, not the levels.

**The worm regeneration paid off completely**: 83.3% undefended harm at 60% natural retrieval,
reduced to 3.3% by B13. The old worm population measured near-zero harm because its instances
did not propagate.

**Exfiltration is still 0% harm, and that now means something different.** The instances are
exfiltration attacks (68.8% by an out-of-loop judge, up from 38%) and they ARE retrieved (53%
naturally), and the agent still never complies. So this is no longer a labelling artifact --
it is a property of qwen2.5:7b in this setup, which belongs with the agent-capability limits in
Scope of claims rather than being reported as a defense result. I previously offered
safety-trained refusal as the explanation and then withdrew it; with correctly-labelled,
confirmed-retrieved instances it is the surviving explanation, but it is an inference about the
agent, not a measurement of the attack class. Same for `authority_impersonation` (0% at 60%
retrieval) and `minja`.

**B12 made policy_revocation worse than undefended** (33.3% vs 26.7%, n=15). Small n and within
noise, but it is in the table rather than smoothed out.

## Attack-side corrections (these change how older numbers read)

**Mechanism validation, first time ever run** (`mechanism_validation.py`, judged by a third
model family):

| Mechanism | instances implementing their own label |
|---|---|
| memory_worm | 26/79 = 33% |
| exfiltration_instruction | 19/50 = 38% |
| minja | 45/52 = 87% |
| agentpoison | 33/37 = 89% |
| farma | 42/46 = 91% |
| authority_impersonation | 50/50 = 100% |
| conditional_backdoor | 50/50 = 100% |
| dsrm | 46/46 = 100% |
| memorygraft | 38/38 = 100% |
| mpbench | 46/46 = 100% |
| policy_revocation | 50/50 = 100% |
| preference_hijack | 50/50 = 100% |
| sleeper_memory_poisoning | 38/38 = 100% |

Eight families are perfectly labelled, so their per-family claims are sound.
**`exfiltration_instruction` at 38% explains why it measured 0 harm across three separate
measurement fixes: most of those instances are not exfiltration attacks.** I diagnosed that 0
as safety-trained refusal, then as no credentials in the store, then as the owner's own
questions. It was none of those, and no amount of fixing the TASK could have moved it.

**Both drifted families were regenerated against a structural spec with a validation loop**
(`validated_regen.py`), keeping only candidates that pass the mechanism check:

| family | before | held-out judge (mistral:7b, out of loop) | generator acceptance |
|---|---|---|---|
| memory_worm | 33% | **90.0%** (36/40) | 97.6% |
| exfiltration_instruction | 38% | **68.8%** (22/32) | 38.1% |

The held-out column is the only admissible model-based evidence: the loop filters with
llama3.1:8b, which is the judge `mechanism_validation` itself uses, so the regenerated
population's mechanism-validation score is circular and the artifact carries a `DO_NOT_CITE`
field saying so.

The worm fix is clean. **Exfiltration is only half fixed, and the acceptance rate says why:**
38.1% of spec-directed candidates pass, which is essentially the 38% rate of the unguided
originals. The spec did not improve AUTHORING at all -- the entire gain comes from filtering --
and a held-out judge still only confirms 68.8%. Exfiltration remains the weakest family in this
benchmark, and the difficulty is in writing the mechanism, not in labelling it.

**Attack success is a property of the attack AND the task it meets.** Two probes of the same
2,328 attacks disagree in both directions -- memorygraft 13%->86% and mpbench 30%->74% under a
fitted task, but minja 88%->19% and dsrm 70%->37%. So no single-task rate is a property of the
attack, and `working_ids()` unions the probes while publishing both.

## Scope of claims: what this benchmark does and does not measure

Stated as limits on the claims rather than as a list of open bugs, because some of these are
not fixable here and a reader needs to know which numbers they bound.

**Agent capability is a floor on every harm number.** All agent-side measurement uses
qwen2.5:7b on a 6GB card. The multi-hop condition is the clearest case: the ORACLE arm hands
the agent perfect evidence and it still answers only 36/60 correctly. A defense cannot be
credited or blamed for the 24 it gets wrong with perfect evidence, so **multi-hop reasoning is
outside what this benchmark measures** -- the 27/60 defended figure should not be read as a
defense result, and no claim in this project rests on it. The same ceiling applies, less
visibly, to every harm rate: they are harm rates for a 7B agent, not for a frontier one.

**Attack success is a property of the attack AND the task it meets**, so no single-probe rate
is a property of an attack. Two probes over the same 2,328 instances disagree in both
directions (memorygraft 13%->86% and mpbench 30%->74% fitted, but minja 88%->19% and dsrm
70%->37%). The union is used for "is this functional"; both probes stay published and their
spread is the honest uncertainty on any per-family rate.

**Detection rates need their working-attack denominator.** 45.1% of instances both subvert an
undefended agent and implement their label (`working_set.py`). Catching 91% of a population
where a third of the items function is a weaker claim than it reads, which is why every rate is
reported on both denominators.

**Threat model for B16.** Rejection memory only engages when an attacker retries against the
same scope's ledger. Single-shot attackers, attackers who distribute attempts across isolated
scopes, and attackers who wait out the TTL are unaffected, and B16's static recall is B15's by
construction.

**One hold-out is informed for B15/B16.** `external_test` was frozen before B14, so B14's
number on it is clean; B15's architecture was chosen after reading that set's baseline results,
so B15 and B16 are only cleanly held out on Mosscap, which was frozen before B15 existed.

**Authorship.** 998 Gandalf + 1,200 Mosscap attacks are human-authored, closing the
LLM-authorship confound for those populations. Everything else is LLM-authored, and the two
model families used (qwen, gemini) are reported separately where it matters.

## What is NOT fixed

- **Adaptive evasion**: ~19% with provenance active vs B12's 21.4% -- unchanged. Provenance
  more than doubles what is caught at round 0 (27/42 vs 13/42) but does not reduce the rate at
  which a defense-aware attacker rewrites past what was caught.
- **No LICENSE** -- the owner's decision, deliberately deferred.
