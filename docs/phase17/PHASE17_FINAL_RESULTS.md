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

## What is NOT fixed

- **Adaptive evasion**: ~19% with provenance active vs B12's 21.4% -- unchanged. Provenance
  more than doubles what is caught at round 0 (27/42 vs 13/42) but does not reduce the rate at
  which a defense-aware attacker rewrites past what was caught.
- **Multi-hop 27/60**: the oracle condition hands the agent perfect evidence and still reaches
  only 36/60. A 7B model's reasoning limit, not a memory-defense problem.
- **No LICENSE** -- the owner's decision, deliberately deferred.
- **Attack authorship**: 998 Gandalf + 1,200 Mosscap attacks are human-authored, which closes
  the confound for those populations. Everything else is LLM-authored.
