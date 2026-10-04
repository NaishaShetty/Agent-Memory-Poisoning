# Phase 17 -- external review rounds 5-6, final results (2026-10-04)

The one-table summary. Recall is exclusion rate; FPR is over the four ordinary benign
populations; cost is cold-cache seconds per admitted memory; the last column is the flag rate
on 40 legitimate standing instructions when provenance records them as the user's own words.

| Config | own attacks (340) | external-dev (266) | external-test (1258) | holdout2 Mosscap (1200) | ordinary-benign FPR | cost | legit-instruction flags |
|---|---|---|---|---|---|---|---|
| B12 | 47% | 34% | 66% | 15% | 0/1074 | 0.17s | 14/40 |
| B13 | 52% | 38% | 71% | 18% | 0/1074 | 0.12s | 2/40 |
| B14 | 48% | 53% | 91% | 54% | 1/1074 | 26.35s | 4/40 |
| B15 | 44% | 44% | 87% | 43% | 0/1074 | 0.29s | 4/40 |

## The four findings that matter most

**1. B13 is the recommendation.** It is the best config on this project's own attacks -- the
populations that actually test memory poisoning -- AND it is **cheaper than B12** (0.71x) while
beating it everywhere. No trade-off.

**2. B14's external result does not generalise.** 91% on external-test, **54% on Mosscap**.
Both are human-authored prompt-injection corpora. A 37-point gap between two sets of the same
kind means neither number is a stable estimate, and the single 91% figure should not be cited
alone. This is why the second hold-out was built before B15 existed.

**3. B14 costs 155x B12** (26.35s vs 0.17s per memory) for that unstable external recall. On
own attacks it is no better than B12 (48% vs 47%).

**4. Provenance is what reaches the hard classes, and it is nearly free.** Pre-registered, run
twice (the second run after a dev-side fix to the evidence-retrieval width, both reported):

| Pre-registered comparison | B12 | B13 |
|---|---|---|
| Additive fabrication (72) | **0** | **37** (p=1e-11) |
| Fabricated preferences (48) | **0** | **27** (p=1e-08) |
| Externally-authored attacks (266) | 90 | 100 (p=0.002) |
| Benign derived memories falsely excluded (1515) | 0 | 7 (0.46%) |

Additive fabrication was documented as unreachable by content-only detection and B12 scores
exactly 0. The benign cost fell from 1.12% to 0.46% when the evidence search was widened from
5 turns to 20 -- fixing the cause rather than weakening the rule.

## How many of these attacks actually work: 47.9%

`attack_validity_audit.py` ran both probes over all 2,328 instances. An attack counts as
working only if the undefended agent complied AND did not comply on the same task without the
memory -- causal, and never consulting any defense's decision.

| Population | generic probe | fitted probe | union |
|---|---|---|---|
| InjecAgent (62) | 52 | 19 | **53 (85%)** |
| zh_native (30) | 21 | 17 | 25 (83%) |
| Track B original (15) | 3 | 11 | 11 (73%) |
| founding_regen (208) | 85 | 110 | 147 (71%) |
| evasion_47 | 15 | 25 | 33 (70%) |
| novel_60 | 33 | 21 | 42 (70%) |
| BIPIA (150) | 89 | 38 | 99 (66%) |
| corpus_extended (138) | 65 | 48 | 91 (66%) |
| frozen75 (34) | **0** | 14 | 14 (41%) |
| Gandalf (998) | 172 | 148 | **265 (27%)** |
| AgentPoison published (6) | 0 | 0 | **0 (0%)** |
| **TOTAL (2,328)** | | | **1,116 (47.9%)** |

**Every detection number in this project needs this denominator beside it.** Catching 91% of
external-test, where 27-48% of the items function as attacks, is a weaker claim than it looks.

**The two probes disagree in both directions and neither dominates** -- InjecAgent 52 generic
vs 19 fitted, Track B 3 generic vs 11 fitted. That is why the union is used for "is this a
functional attack" (an attacker chooses the context) while both individual probes stay
published as the honest uncertainty.

**`frozen75` went 0/34 generic to 14/34 fitted**, which rescues the coordination/GNN work: its
poisons do function, they just need a task that gives them an opening. **`AgentPoison
published` is 0/6 under both probes**, so its detection numbers have no behavioural consequence.

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
measurement fixes: most of those instances are not exfiltration attacks.** The mechanism is
untested, not disproven. `memory_worm` at 33% is the 30 original non-implementing instances
still sitting in the population beside the 29 corrected ones; they need removing, not just
superseding.

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
