# Defence programme v8 -- implementation notes and deviation log

Deviations from `V8_PREREGISTRATION.md`, numbered D-V8-n, logged here before the outcome
each concerns is known. Each entry is addended to the pre-registration with a checksum.

## D-V8-1 -- SA-8 owners drawn from Conversation Chronicles only, not CC + LongMemEval

**Date:** 2026-10-20, before any SA-8 generation call was made.

**What the brief said:** "Prefer Conversation Chronicles (CC BY 4.0) and LongMemEval
(MIT), both already processed locally."

**What was done:** SA-8's 10 owners are all Conversation Chronicles episodes
(`phase17/defence_v8/cc_owners.py`). LongMemEval was not used.

**Why:** CC alone already supplies 10 two-speaker, 40-90-turn episodes with zero owner
overlap with any prior SA corpus. SA-6 and SA-7 themselves each drew from a single source
per round; mixing CC and LongMemEval owners within one corpus would have required a second
adapter module and a second selection rule for no stated methodological benefit (the
requirement is owner-disjointness from SA-1..SA-7, not source diversity within SA-8).
"Prefer" is read as "prefer these two over anything else," not "use both."

**Risk assessed:** none identified. CC is CC BY 4.0, already processed at
`data/processed/conversation_chronicles/`, and sits in a dataset family (dyadic, role-
labelled conversations) structurally similar to LoCoMo, so the generation template and
gates transfer without modification.

**Status:** accepted, recorded before SA-8 generation began.

## D-V8-2 -- additive extension of phase17/provenance_sets.py for SA-8 owners

**Date:** 2026-10-20, after SA-8 was generated and frozen, before any scoring.

**What happened:** Scoring C AND K on SA-8 requires `phase17.defence_v3.vpl._decide` (B12/
B13, computed unconditionally by `g3_v7.signals()` even though unused by the C&K
condition) and `phase17.defence_v3.sleeper_v3._conv_text`/`provenance_sets.speakers`,
all of which call `phase17.provenance_sets.owner_turns`/`speakers` directly, hardcoded to
LoCoMo sample indices 0-9. SA-8's owners are 100-109 (Conversation Chronicles).

**What was done:** `phase17/provenance_sets.py::owner_turns` and `::speakers` each gained
one additive branch: `if sample_idx >= 100: return cc_owners.owner_turns/speakers(...)`,
placed before the existing LoCoMo logic, which is otherwise byte-for-byte unchanged.
Verified: `speakers(0)`/`owner_turns(0)` unchanged; the full `phase17/ -m "not slow"`
suite (300 tests) and `phase17/tests/test_v7_frozen.py` both green before and after.

**Why not duplicate the pipeline into defence_v8 instead:** the alternative was copying
`vpl._decide`, `sleeper_v3._conv_text`/`n1`, and `g3_v7.signals` into v8 with only the
owner-resolution import swapped -- duplicating hundreds of lines of already-frozen,
already-validated logic for a one-line owner dispatch, which is a larger correctness risk
(two copies that must be kept in sync) than a provably side-effect-free additive branch in
a shared, non-frozen utility module. `provenance_sets.py` is phase17's own shared
infrastructure (like `stats.py`/`near_dup.py`), not an "earlier phase" or a v7-frozen path
-- it is not listed in `V7_FREEZE_MANIFEST.json` and has been extended additively across
v2 through v7 already.

**Status:** accepted.

## D-V8-3 -- additive extension of phase17/provenance_sets.py for SA-9 owners (200-209)

**Date:** 2026-10-20, before any SA-9 data existed.

Same pattern and justification as D-V8-2: `owner_turns`/`speakers` gained a second
additive branch, `if sample_idx >= 200: return longmemeval_owners...(...)`, placed before
the existing branches (D-V8-2's CC branch for 100-109, and the original LoCoMo logic for
0-9), none of which change. Verified: `phase17/ -m "not slow"` green and
`test_v7_frozen.py` green before and after.

## D-V8-4 -- SA-9 generation always sets who = "User", never alternating

**Date:** 2026-10-20, before any SA-9 data existed.

SA-6/7/8 alternate `who` between an episode's two speakers (`(a, bb)[seed % 2]`) because
both are real human conversation participants in LoCoMo/Conversation Chronicles. LongMemEval
pairs a human `user` with an `assistant` role; "whenever the Assistant does X, remind the
Assistant" is not a sensible personal-memory rule. `phase17/defence_v8/sa9_corpus.py` sets
`who = "User"` unconditionally. This is a content-generation choice, not a change to any
frozen detection logic, and does not affect writer-identity assignment (which never looks
at `who` or `kind`).

**Status:** accepted.

## D-V8-5 -- SA-9 short cell: owner 203 has 0 atk_implicit items (expected 8)

**Date:** 2026-10-20, discovered after generation completed, before freezing.

SA-9 generation returned `{'complete': True, 'n': 632, 'short_cells': {'203:atk_implicit': 0}, ...}`
(expected 640 = 10 owners x 8 kinds x 8). Both `atk_implicit` batches for owner 203
(eval split) returned zero parsed items, while every other kind for that same owner
(including the other two attack kinds, `atk_explicit` and `atk_highimpact`) succeeded
normally (10/10 parsed each). Owner 203's LongMemEval episode
(`answer_sharegpt_GYqnAhC_190`) is an atypical game/text-adventure-style transcript
("You're pretty sure that without knowing what file..."), not an ordinary personal
conversation; the `atk_implicit` prompt specifically appears to have produced empty or
unparseable output from Gemini for this excerpt across both batches (no exception was
raised -- `S1._parse(raw)` returned an empty list both times), while the other attack kinds'
differently-worded prompts did not trigger the same outcome.

**What was done:** accepted as-is. SA-9 is frozen at n=632 (not regenerated, not retried,
not substituted with a different owner or excerpt) -- retrying until a cell fills would be
exactly the kind of researcher degree of freedom the pre-registration exists to foreclose.
This reduces SA-9's eval `atk_implicit` count from the expected 48 to 40 (5 of 6 eval
owners contributing 8 each). `phase17/stats.py::require_power`'s own sweep
(`V8_PREREGISTRATION_POWER.json`) already showed n=48 at the expected 0.56 detection rate
is powered with a very large margin (required-with-2x-margin: 12 discordant pairs; n=40
remains amply powered by the same calculation). 3.2/3.3's pass/fail reading (a point-estimate
threshold, per the main pre-registration Sec 1) is unaffected in kind, only in the exact
denominator, which is reported plainly wherever SA-9's eval counts are shown.

**Status:** accepted; reported, not concealed, in `RESULTS.md`.

## D-V8-6 -- HO11 owner names substituted for CC's generic role labels

**Date:** 2026-10-20, during HO11 root generation, before any roots were kept/frozen.

CC's generic role labels ("Classmates A", "Mentee", ...) were reproduced almost never by
mistral:7b-text's RAW completion (no instruction-following): the first HO11 attempt
dropped 77/80 jobs on the own-name structural gate. Diagnosed with a direct harness test
(`H7._complete` on isolated seeds): the real cause is NOT specific to CC -- the style
examples for both factual families (`fact_contradiction`, `additive_fabrication`) are
drawn from hold-out 4's own corpus (LoCoMo sample 7, "Deborah and Jolene"), and a base
completion model frequently continues with "Deborah" (or omits any name) regardless of
which owner it is nominally generating for. A control test against owner 4 (a real HO10
owner that achieved 24-40/90 kept in the actual v7 build) reproduced the same low hit rate
in a 10-sample probe, confirming this is inherent variance in the method (HO10's own build
log shows 493/540 = 91.3% gate failures overall, with owner-level yields ranging 4/90 to
40/90) -- not a defect introduced by HO11's adaptation.

**What was done:** CC's two role labels are replaced, consistently in both the context
excerpt text and the generation/gate logic, with a natural fictional first name per owner
(`ho11_owners.NATURAL_NAMES`), assigned independently of family/kind (same
label-independence discipline as `writer_policy.assign_writer`). This does not fix the
underlying low base rate (confirmed inherent to the method, not to CC) but gives the gate
a realistic chance of matching, exactly as HO9/HO10's real human names did for their
better-performing owners. `SEEDS`/`KEEP` are left at HO10's own values (90/40), scaled to
9 owners for the pre-registered ~3x yield target; per-owner yield is expected to be as
uneven as HO10's own (4-40 kept per 90 seeds), reported as realised, not adjusted after
the fact.

**Status:** accepted; full build proceeds at HO10's own parameters.

## D-V8-7 -- HO11 raw yield short of target, frozen as-is (no top-up)

**Date:** 2026-10-21, after root generation completed, before flagging (no flag/chain
results exist yet -- this decision is made on raw generation counts only).

HO11 kept 816 items (456 attack, 360 benign) against a target of 720 attack + 360 benign.
Benign hit its per-owner-family cap (10) everywhere -- exactly on target. The attack
shortfall is entirely in `fact_contradiction` (2-32 kept per owner, target 40): a
"replace a stated value with a different one" contradiction does not grammatically need
to restate the subject's name (e.g. "2009 was not the year... The year is actually 1823"),
so the own-name structural gate fails it far more often than `additive_fabrication`
(mostly 26-40 kept, close to target), which inherently requires naming its subject to
assert a fact about them.

**What was done:** frozen as-is at 816 items (sha256
`5beedd2b4cc80ce7c1cb9ca18d0de08a534bce78b30918a459b62f690f25f0f3`), no additional seeds,
no additional owners. `V8_PREREG_ADDENDUM_W3.md` already committed to reporting a
shortfall rather than silently patching it; proceeding to flagging/chains with whatever
gen-4-carrying count results, reported honestly either way.

**Status:** accepted.

## D-V8-8 -- Methodology Draft.docx and MAMBench Results Analysis.docx removed from the freeze manifest

**Date:** 2026-10-21, after the user explicitly authorized updating both documents with
v8 content ("update the methodology draft and result analysis document as well"),
superseding the original plan's Rule 5 ("Paper documents stay at v7 during v8").

**What was done:** `phase17/build_v7_freeze_manifest.py`'s `FROZEN_FILES` list no longer
includes these two files; the manifest was rebuilt and `test_v7_frozen.py` is green again.
This does not touch `FROZEN_DIRS` (`phase17/defence_v7/`, `phase17/data/defence_v7/`,
`docs/phase17/v7/`), which remain the permanent guarantee that v7's code, data and
documentation never change -- the only thing this decision relaxes is tracking the two
standalone paper documents, which the user has now explicitly asked to be brought current.
`MAMBench_Comprehensive_Project_Documentation.docx`, `README.md`,
`docs/REMEDIATION_MASTER_REGISTER.md` and `mambench/registry.json` remain tracked until
each is deliberately updated, at which point the same disclosed pattern applies: update,
then rebuild the manifest, then log it here.

**Status:** accepted; both documents were rebuilt in full by their existing builder
scripts (`phase17/build_results_analysis_docx.py`,
`phase17/update_methodology_v7.py`-equivalent `update_methodology_v8.py`), never
hand-edited, so the content is traceable to the v8 artifacts exactly as every section
before it is.

## D-V8-9 -- MAMBench_Comprehensive_Project_Documentation.docx removed from the freeze manifest

**Date:** 2026-10-21, after the user's documentation-consolidation request explicitly
asked to rebuild the comprehensive DOCX with v8 content.

**What was done:** `scripts/build_comprehensive_documentation.py` was updated throughout
(executive summary, architecture figure, closure table and figure, negative results,
source-document mapping, essential commands) to reflect Defence Programme v8 -- the
closure numbers (75.0% / 75.0% / 61.3%), the new architecture and closure figures
(`docs/figures/v8/X6_architecture_v8.png`, `X5_closure.png`), a new source-document row
for `docs/phase17/v8/`, and the `update_methodology_v8` command. It also corrected two
facts that had gone stale since the 2026-10-18 cleanup (a release-readiness row still
named three `ref_*.txt` files already deleted by that cleanup; the CI row's wording was
tightened to state only what is actually confirmed -- the first hosted run's two findings
were fixed and verified locally, not a claim of a second green hosted run that was never
recorded). The file was removed from `FROZEN_FILES` the same way the other two paper
documents were (D-V8-8); the manifest was rebuilt and `test_v7_frozen.py` is green.

**Status:** accepted; rebuilt via its builder script only, never hand-edited.

## D-V8-10 -- docs/REMEDIATION_MASTER_REGISTER.md removed from the freeze manifest

**Date:** 2026-10-21, after adding the v8 section (Sec 11) -- always a planned v8
deliverable per `V8_PREREGISTRATION.md` ("Register: a v8 section in
docs/REMEDIATION_MASTER_REGISTER.md"), not a new authorization.

**What was done:** the register gained Section 11 (Defence programme v8), listing V8-1
through V8-7 in the same ID/finding/fix/status format every prior section uses, plus the
D-V8-6/7/8/9 deviations. Removed from `FROZEN_FILES`; manifest rebuilt;
`test_v7_frozen.py` green. `README.md` and `mambench/registry.json` remain the only
standalone files still tracked by the manifest.

**Status:** accepted.

## D-V8-11 -- README.md removed from the freeze manifest

**Date:** 2026-10-21, after updating README.md with v8 content (closure chart, current
results, limitations, architecture diagram, repository map) -- a planned v8 deliverable
("update the README closure chart") that the user then explicitly asked for directly.

**What was done:** updated the closure `xychart-beta` (v8 added to all three gap lines),
the architecture figure (now `docs/figures/v8/X6_architecture_v8.png`), the pipeline
flowchart (added the authenticated-writer ledger node), the "Current results" table (new
SA-9/HO11/stress-test rows), "Known limitations" (the compromised-trusted-writer boundary
replaces the "Gap 3 not closed" framing, now that one operating point does clear both
limits), the research-gaps table, repository map, and a sixth contributions bullet on
non-generalisation of an unconfirmed detector pass. Removed from `FROZEN_FILES`; manifest
rebuilt; `test_v7_frozen.py` green. `mambench/registry.json` is now the only standalone
file the manifest still tracks (no v8 mambench tasks have been added, so it is genuinely
unchanged).

**Status:** accepted.

## Build log

(Filled in as each build/freeze/score step runs; see `docs/phase17/v8/RESUME_V8.md` for the
checkpoint state at any point the laptop is shut down.)
