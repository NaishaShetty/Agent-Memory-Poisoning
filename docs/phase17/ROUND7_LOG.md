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
