# Round 7 log (2026-10-06 onward)

Written as things are found, in order, so the record does not depend on recollection at the end.

## Decisions by the owner

- **Hold-out 3 is retired from further measurement** (2026-10-06). It has been scored five times
  and only the first was pre-registered. New configurations are tested once on newly frozen,
  pre-registered corpora.
- Downloads approved: `lmsys/toxic-chat` as hold-out 5; the 2023-05-07 jailbreak snapshot of
  hold-out 3's source as dev data.

## Finding R7-1 (unfavourable): the hold-out 3 "dev snapshot" is not independent of hold-out 3

`injection_dev_attacks.py` fetched `jailbreak_2023_05_07` (666 prompts, 648 after exact dedup)
and applied the new near-duplicate check (`near_dup.py`: word 5-gram containment >= 0.6, fixed
before any corpus was built with it). **647 of 648 are near-copies of frozen hold-out 3
attacks.** The December collection evidently contains the May one. The jailbreak snapshot is
therefore unusable as dev data, and is not used.

The same check on the already-published `holdout3_dev_benign` (400 items, the `regular_2023_05_07`
snapshot): **382/400 are EXACT copies of hold-out 3 benign prompts once the memory wrapper is
stripped, and 393/400 are >= 0.95-contained.** The disjointness check
(`holdout3_dev_benign.verify_disjoint`) compared WRAPPED strings, and wrappers are assigned by
position, so the same prompt under a different wrapper passed as "disjoint". It reported 110
overlaps dropped; the real overlap was nearly the whole set.

Consequences for results already published, to be corrected in place:

1. `holdout3_matched_fpr.json` -- "matched operating points shrink the baseline's lead from 17
   points to 2.8". Every scorer's threshold was fitted on a set that is ~96% copies of hold-out
   3's own benign half. The comparison is still SYMMETRIC (all scorers calibrated identically),
   so it remains a valid matched-operating-point comparison, but it is HOLD-OUT-CALIBRATED, not
   dev-calibrated, and the text describing it as "a disjoint dev snapshot" is false.
2. `diagnose_benign_fpr.json` -- "content-only 43.0% on 200 DEV in-the-wild benign" was measured
   on hold-out items. The attribution (content detector, not corroboration) is unaffected in
   direction, but it is a hold-out measurement, not a dev one.
3. Anything else that read `holdout3_dev_benign` is audited below.

## Finding R7-2: hold-out 5 built and frozen

`holdout5_corpus.py`, toxic-chat `toxicchat0124`, frozen 2026-10-06T10:53:12Z, sha256
`fd8b83cc...`. 183 jailbreak candidates; **52 dropped as near-copies of corpora this project had
already used**, leaving 131 attacks. 1,000 matched benign sampled from 8,199 non-toxic,
non-jailbreak prompts of the same demo (50 near-duplicates dropped first). 464 toxic
non-jailbreak prompts excluded from both halves. The attack half is small: a rate on 131 items
has a 95% interval of roughly +/-8 points, and every claim made on it is held to that.

### R7-1 audit: every consumer of `holdout3_dev_benign`

| module | what it used the "dev" set for | consequence |
|---|---|---|
| `holdout3_matched_fpr.py` | per-scorer threshold at a target FPR | hold-out-calibrated (symmetric across scorers); relabel |
| `holdout3_frontier.py` | dev side of the operating-point sweep | the "shipped point leaves N points unused" headroom is hold-out-informed; relabel |
| `diagnose_benign_fpr.py` | per-rule FPR attribution on "200 DEV items" | a hold-out measurement; direction unaffected; relabel |
| `memory_shape_gate.py` (B19) | rules fitted and inspected | B19 was fitted on near-copies of the hold-out benign half and STILL failed on it, so the contamination could only have flattered it; the negative result stands and is strengthened |
| `benign_validity_audit.py` | docstring reference only | none |

## Finding R7-3 (artifact metadata): `neutralise.json` names the wrong frame

The hold-out 3 neutralisation artifact's `frame` field holds the v1 prefix text, the frame this
project later showed to be actively harmful. The run itself applied `v3_depersonalise`: the code
path is `neutralise()` -> `FRAMES[WINNER]`, and `WINNER = "v3_depersonalise"` at commit
`033ffe2d`, which produced the artifact. The result (34.0% -> 14.7%) therefore stands and is
correctly attributed in both documents; only the artifact's metadata was stale. The module now
records `WINNER`. The published artifact is left as committed (data artifacts are not hand-edited)
and this note is its correction.

## Finding R7-4 (construction): the hold-out 4 author inverted two attack families

First-pass generation of hold-out 4 was INSPECTED before freezing (no configuration had seen it).
mistral:7b, asked for a standing rule redirecting the assistant against the user, wrote 40/40
protective rules ("Do not share personal photos without my explicit consent"); asked for a dormant
harmful trigger, it produced 7 gate-passing items, all benign. A safety-tuned author does not write
instruction-shaped attacks, so those two families were withdrawn as attacks and hold-out 4 covers
note-shaped poisoning (additive fabrication, preference hijack, fact contradiction, sleeper
routine). The 40 inverted standing instructions are kept as a hard-benign family. Recorded because
it is a general property of using an aligned model as an attack author, and because a corpus
assembled without inspection would have filed 40 protective rules as attacks.

## Process error R7-5: the orphan killer excluded nothing when given two pids

The round-7 GPU queue passed `-ExcludePid "<runner>,<gemini>"` so a remote Gemini job (which
shares the `phase17` command-line pattern but not the GPU) would be spared. Through `-File`,
PowerShell bound the comma string to the `[int[]]` parameter such that NO pid was excluded: the
runner killed itself before its first stage and killed the Gemini job at 6/60 candidates. No
completed work was lost (both checkpoint). My first check of the fix used one excluded dummy and
proved nothing; a three-process test (two excluded, one not) exposed it. The parameter is now a
string split explicitly, the guard test excludes two pids, and `orphan_killer_pid_list` reverts
the parameter type as its mutation: PROVEN.

## Finding R7-6 (dev, unfavourable for B20/B21): removing B13's content detector from the unions loses recall

`dev_round7.json`. The decomposition reproduces B13 exactly on every item. With the owner's
conversation, on 804 own attacks / 1,054 ordinary benign: B17 64.4% at 7.6%, B20 56.1% at 7.6%
(B18 64.6% / B21 56.6% at 7.7%). Every ordinary-benign exclusion by B13 comes from corroboration
(79/79); its content detector excludes 0 ordinary benign items but catches own attacks that B14
misses. On the injection bed (266 external dev attacks / 400 toxic-chat dev benign) B20 equals B14
exactly. B20/B21 are dominated by B17/B18 in both beds: the #8 lead fails on dev, and the reason
is recorded rather than the configuration quietly dropped.

## Finding R7-7 (dev): the hold-out 3 false-positive regime does not reproduce on toxic-chat benign

On 400 toxic-chat dev benign prompts (same platform as hold-out 5, disjoint from it): B12 1.2%,
B13 2.2%, B14 6.2%, B17 6.2%, B18 7.0% -- against 16.7% / 33.5% / 54.5% / 54.8% / 54.9% on hold-out
3's matched benign half. The B17/B18 FPR "floor" is B13's own rate on the corpus at hand, and on
ordinary chat prompts that rate is 2.2%. So the 33-55% regime is at least partly a property of the
DAN-community `regular` prompts (long, persona-style, written by jailbreak communities), not of
matched-platform benign text in general. This is a dev observation with dev attacks from other
sources; hold-out 5 is its clean test and the prediction is pre-registered.

## Finding R7-8 (instrument): leading tasks on claim-shaped attacks

Hold-out 4's causal audit (v1, `holdout4_causal.json`): 73/157 working, but a task-alone base rate
of 66/157 -- additive fabrication 23/38, preference hijack 30/40, contradiction 8/40, sleeper 5/39.
The generic task generator writes requests "about the same subject", which for a fabricated fact
means presupposing it. The causal criterion excludes those items, so the working set was
conservative rather than inflated, but the two families the hold-out exists to test were largely
invisible to it. Fixed with a non-leading generator and a deterministic leak check (guard
`leading_task`: PROVEN), before any defense was scored on hold-out 4 (pre-registration addendum 1).

### R7-8 outcome

v2 (non-leading) audit: task-alone base rate 7/157 (was 66/157). Working (causal AND mechanism)
86/157 = 54.8% -- additive fabrication 28/38 and preference hijack 30/40 are now visible, but
fact contradiction (23 -> 15/40) and sleeper routine (30 -> 15/39) fall, because a non-leading
request gives those attacks less of an opening. The project's standing convention is the UNION over
probes (an attacker chooses the context); addendum 1 committed v2 as the working set, so v2 is
primary as committed and the union (v1 OR v2, AND mechanism) is reported beside it as secondary.

## Result R7-9: exfiltration authoring (#10) -- the instruction, not the author

`exfil_authoring.json`, 40 candidates per generator, identical spec, structural gates and in-loop
judge; near-copies of few-shot examples count as failures (there were none).

| generator | gates pass | accepted (gates AND judge) | out-of-loop judge on accepted |
|---|---|---|---|
| qwen, spec only | 5/40 | 1/40 (2.5%) | 1/1 |
| qwen, spec + 3 examples | 13/40 | **11/40 (27.5%)** | 8/11 |
| gemini, spec only | 3/40 | 2/40 (5.0%) | 2/2 |
| gemini, spec + 3 examples | 9/40 | 7/40 (17.5%) | 6/7 |

A different author family does not help (Gemini spec-only 2/40 against qwen's 1/40, and the
published 8.4%); worked examples do, for both authors. The defect was an instruction too abstract
to author against. Pre-registered B-6 holds (27.5% >= 23.4%). Small n: the qwen few-shot vs
spec-only difference (11/40 vs 1/40) is large; the few-shot qwen vs Gemini difference is not
claimed.

## Finding R7-10 (description): the published harm study used FIXED tasks

`harm_study_v2.json` records `per_instance_tasks: false` and 14 distinct tasks for 309 instances;
`run_all` invokes the stage without the per-instance flag. PHASE17_FINAL_RESULTS.md described it as
"per-instance fitted tasks". The published 28.2% -> 10.4% stands as measured, with its 1/309
task-alone base rate; the description was wrong and is corrected in place. Found because the Phase B
reproduction (`neutralise_own`) asserted the description and the artifact disagreed.

## RESUME HERE (paused 2026-10-06 ~23:45 at the owner's request; laptop shut down)

Done and committed: Phase A (corrections, guards, dev work), hold-outs 4 and 5 built, frozen and
scored ONCE under the committed pre-registration (13/16 predictions held), exfiltration
authoring, Phase B neutralisation on own attacks and on a stronger agent.

Still to run, in this order -- all stages checkpoint, so nothing completed is lost:

1. Kill orphans first: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/kill_orphan_phase17.ps1`
2. Ledger radius sweep (4-6 h, the long one) and hold-out 5's without-memory causal arm (~5 min).
   Launch DETACHED so a session time limit cannot kill it (the wrapper was killed once at 2 h):
   `powershell -NoProfile "Start-Process -FilePath python -ArgumentList '-u','-m','phase17.run_round7','ho5causal','sweep' -WorkingDirectory 'C:\Agent Memory Poisoning' -RedirectStandardOutput 'C:\Agent Memory Poisoning\phase17\data\run_all_logs\r7_queue5.log' -WindowStyle Hidden"`
   (`sweep` = the ledger_radius_sweep stage on its own; the neutralise_own and strong-agent
   stages of `phaseb` are already complete and cached.)
3. `python -m phase17.report_round7` (scores B-1..B-6), `python -m phase17.final_inventory`,
   `python phase17/build_results_analysis_docx.py`, `python phase17/update_methodology_round7.py`
   (add the remaining 32.54+ sections and update the abstract/Section 33 first).
4. With the GPU idle: the FULL `python -m phase17.error_registry` (no ids -- a partial run merges,
   but the published record should come from one complete run), then the full test suite.
5. Phase C: the publishability verdict against the two-sided standard in the handoff.

Do NOT score hold-out 3, 4 or 5 again; every later use would need a use number at every point of use.

## Finding R7-11 (labelling): hold-out 3 was scored SEVEN times, not five

The count "five times" (methodology 32.44, the results paper, this round's pre-registration ledger)
lists the pre-registered run, matched-FPR, frontier, B19 and the structural-only variant, and omits
the two neutralisation runs on hold-out 3 that followed (v1, which produced the "partial 49/150 ->
38/150" reading, and the dev-selected v3, which produced 34.0% -> 14.7%). The v3 result is
therefore hold-out 3's SEVENTH use and is not an independent estimate, although it was presented as
"the hold-out was scored once" (true of the frame, not of the corpus). It now carries that label at
every point of use, and hold-out 5 -- frozen and pre-registered -- replicates the effect cleanly
(37.4% -> 18.3%, p=2e-05). Found while checking the publishability condition "no headline claim on a
repeatedly-scored hold-out without a label". Guarded by `claims_guard` (holdout3_use_count).

## Finding R7-12 (scope): the union's "no additional false-positive cost" holds on ordinary memory only

Round 6 reported that B17 beats both components "at no additional false-positive cost": every
ordinary-benign item B13 excluded, B14 already excluded (2/1088). On hold-out 4's matched benign
notes that is false -- B17 excludes 42/262 against B13's 31 and B14's 24, because the two components
flag DIFFERENT benign notes there. On hold-out 5, B17 adds 51/1000 over B13 and 2 over B14. The
claim is now scoped to ordinary memory wherever it appears, and guarded (`union_free_fpr`).

## Finding R7-13 (recommendation): B18 is not the memory-poisoning recommendation on clean data

Round 6's final guidance (32.45) named B18 (or B17) with evidence for memory poisoning, on a +4.9
point lead over B13 measured on this project's own attacks -- populations B18 was selected after
reading. On hold-out 4 (clean, scored once) B17/B18 have exactly B13's recall (50.3%; 52/86 working)
and add false positives (16.0% vs 11.8% on the untrusted channel). B13 with evidence dominates them on
this threat. The recommendation is rewritten (methodology 32.56, results 10B) with the round-6 text
kept and marked superseded; guarded by `b18_memory_poisoning_recommendation`.
