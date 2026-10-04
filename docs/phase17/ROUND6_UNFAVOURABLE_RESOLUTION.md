# The 20 unfavourable outcomes, and what happened to each (round 6, 2026-10-04)

The instruction was to fix all 20 without compromising integrity. Three of them could not be
"fixed" in the sense of producing a better number, and are recorded as scoped-out limitations
instead -- saying so is the only honest option, and quietly dropping them would have been the
easier one. Two came out worse than the previous write-up claimed, and that is recorded too.

Measurement artifacts: `phase17/data/eval_round6.json`, `attack_validity_audit.json`,
`working_set.json`, `recall_on_working.json`, `validated_regen.json`,
`baseline_breakdown.json`, `rejection_memory_config.json`, `eval_rejection_memory.json`.

## The structural fix underneath most of them

Nine of the twenty were instances of one defect: **no population was ever filtered by whether
its members do what they claim.** The worm population had stopped propagating, the exfiltration
population never exfiltrated, the published AgentPoison records were measured outside their
trigger five times, and Mosscap was a headline hold-out column that appeared in no audit at all.
Each had been fixed individually, late, after numbers were published on top of it.

`phase17/working_set.py` makes the filter explicit and defense-independent: an instance counts
only if it causally subverts an undefended agent AND implements its labelled mechanism. Neither
input consults any defense's decision. The full populations stay published and every rate is
reported on both denominators. Per-population floors are recorded, so a population that drifts
later **breaks CI instead of quietly diluting the benchmark** -- that is the part that scales.

| # | Unfavourable outcome | Status | Result |
|---|---|---|---|
| 1 | B14 91% external-test vs 54% Mosscap -- unstable, neither citable | **Diagnosed, half fixed** | Gap is 36.6 pts full, **20.6 pts on working attacks, p=0.0001**. ~16 pts was composition (Mosscap 21% working vs 31%); the rest is real. 91% still not citable alone, now quantified. Required putting Mosscap into the audit for the first time. |
| 2 | Only 47.9% of attacks actually work | **Fixed structurally** | Working set 1,117/2,628 = 42.5%, per population, with CI floors. Recall-on-working now reported for every config and recomputable without a re-run. |
| 3 | Off-the-shelf deberta nearly matches the bespoke defense | **Refuted** | Composition artifact. B13 **+38.8 pts** on 596 own attacks (53.9% vs 15.1%). Deberta's only win is Gandalf at 99.5% = 47% of the pooled denominator. Pooled comparison marked do-not-cite. |
| 4 | B14 costs 170x B12 for an unstable gain | **Resolved** | Retired as a recommendation in `defended_retrieval.py` where configs are chosen. Superseded: B17 dominates B14 at the same FPR and cost. |
| 5 | Adaptive evasion ~19-21%, unchanged by any config | **New defense built** | Diagnosed as statefulness, not accuracy -- B14's 170x buys nothing here. B16 = per-scope rejection ledger. Radius 0.97 fitted on dev. See the pending row below. |
| 6 | AgentPoison published 0/6 working | **Fixed** | **0/6 -> 3/6**, task-alone base rate 0. Measurement error all five times, not a weak attack. |
| 7 | Multi-hop only 36/60 even in the oracle condition | **Scoped out** | A 7B agent's reasoning limit. Declared outside what the benchmark measures; the 27/60 defended figure is not a defense result and no claim rests on it. |
| 8 | memory_worm 0/30 implementing its mechanism | **Fixed** | Regenerated with a validation loop: 33% -> **90.0%** by an out-of-loop judge. |
| 9 | exfiltration_instruction only 38% correctly labelled | **Half fixed** | 38% -> **68.8%** out-of-loop. But generator acceptance is 38.1%, i.e. the unguided rate, so the spec did not improve authoring -- the gain is entirely filtering. Still the weakest family. |
| 10 | Two populations in no evaluation table at all | **Fixed** | `corpus_extended`, `frozen75`, `founding_regen` (208, scored 0 in round 5) now scored; also caught `zh_translated` silently falling out of round 6, which would have left the Chinese confound finding with nothing to compare against. |
| 11-13 | Mechanism validation never run; no formula-drift guards; probe disagreement unreported | **Fixed** | `mechanism_validation.py`; drift guards in 4 test files; both probes published per population with a guard asserting the refuting cases stay visible. |
| 14-20 | My own recurring errors: orphaned GPU jobs, non-atomic caches, trigger-condition errors, selective reporting, conditional framing, circular validation, manual stage chaining | **Fixed structurally** | Guard tests for the *reporting* failures, not just the code ones, plus `run_all.py`: one command, declared dependencies, orphan kill between GPU stages, resume from checkpoints, guard tests at the end. |

## What came out worse than previously written

**"B13 is the recommendation" was wrong, unqualified.** On working attacks B14 **strictly
dominates** B13 on the clean hold-out (40/64 vs 8/64, +32/-0, p=5e-10). B13's 12.5% on working
Mosscap attacks is a genuine weakness that was not in the previous write-up. B13 and B14 turn
out to be complementary rather than ranked -- B13 reaches poisoning shaped like an ordinary
personal note, B14 reaches injection-shaped text -- so they miss disjoint sets.

That produced the one genuinely new favourable result of the round: **B17 = exclude if either
excludes**, better than both on three of four groups, tied on the fourth, adding **no false
positive at all**, computed from already-saved per-item decisions with no new model calls. It
introduces no parameter, which is what keeps choosing it after reading hold-out results
defensible. Its numbers are descriptive, not a clean held-out estimate.

**The own-attacks column is not comparable to round 5's.** It is 804 instances now, not 340,
because two harder populations were added. B13's own-attack rate reads 46.1% against the
previously published 52% for that reason, not because anything regressed.

## Errors I made during this round

**The AgentPoison trigger error, a fifth time.** I wrote a guard test to make the four previous
occurrences impossible, and it failed on the fix I had just committed: a generic `'([^']+)'`
regex matched the possessive apostrophe in "Caroline's" and produced a query carrying no trigger
at all, live in a running audit. Extraction now targets the records' own structural phrasing.

**The rejection-memory dev fit, wrong in a way that would have killed the idea.** I measured
benign-to-*benign* similarity, read off a 20.8% false-positive rate, and would have concluded
the mechanism was unaffordable. The ledger never contains benign text -- only rejected attacks
-- so the quantity that matters is benign-to-rejected-poison similarity, which is 0.0% at every
threshold in all 7 benign populations. That also means false positives are not the binding
constraint, so the radius is set by bounding the ledger-poisoning blast radius instead.

**My cleanup script killed my pipeline runner.** `kill_orphan_phase17.ps1` matches any python
process whose command line contains "phase17", and `run_all.py` is one. The orphan-reaper became
the orphan-maker on first use.

**My own guard test matched its own docstring.** The B17 no-parameter test scanned source text
for "threshold" and matched the sentence saying B17 is *not* a threshold. It parses the AST now.

## Still open, honestly

- **Adaptive evasion beyond retry-against-one-scope.** B16 does nothing against a single-shot
  attacker, one who distributes attempts across isolated scopes, or one who waits out the TTL.
- **B17 and B16 are not composed.** Everything except B16 is stateless; adding the ledger to
  B17 is the obvious next step and is not done.
- **B15/B16/B17 have no per-population baseline breakdown.** Round 5 predates them.
- **Exfiltration authoring**, per row 9.
- **One hold-out is informed** for B15/B16/B17, so Mosscap is their only clean one.
- **No LICENSE** -- the owner's decision, deliberately deferred.
