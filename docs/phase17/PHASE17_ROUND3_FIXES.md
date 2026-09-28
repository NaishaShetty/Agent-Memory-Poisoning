# Phase 17 Round 3 — Addressing Every Remaining Item Honestly

Trigger: user asked to fix everything from the "anything left to address" list, "make
sure to do it properly," and to fix undesirable results where possible. This document
covers what changed; §11.5/§18 elsewhere in the Phase 17 reports keep the still-open
items current.

## 1. Evasion / additive fabrication — genuine provenance fix, honestly scoped

**Root cause (restated):** the conflict check needs a topically related earlier memory
to compare against; the general 47-variant evasion arena's 3 random distractors never
provide one.

**Real fix:** the 13 gold-bearing poison parents (9 REAL-DSRM/FARMA/MPBENCH + 4
REGEN-DSRM/FARMA/MPBENCH/SLEEPER) each come from a REAL LoCoMo QA pair. Their real home
conversation was located empirically (`phase17/evasion_real_context.py`: each parent's
own `target_question` matched verbatim against every LoCoMo sample's real `qa` list — not
assumed, not fabricated). Using that conversation's own 369–680 real turns as the
"earlier memories" the conflict check compares against — instead of 3 unrelated
distractors — is genuine provenance this benchmark's arenas simply were not wired to use.

**Result:** 6/26 evasion variants of these 13 parents now excluded (23.1%, up from 3/26
in the earlier random-distractor setup), driven entirely by the FARMA family (which
explicitly appeals to prior authority — "already settled from before" — exactly what the
appeal-to-prior-authority test catches). **DSRM and MPBench remain uncaught even with the
full real conversation available** — DSRM's date discrepancies don't clear the conflict
threshold against the real text, and MPBench's fabrications are additive (contradict
nothing) regardless of how much real context is supplied. 0/20 false positives on the
same real conversation's own held-out turns.

**Scope, disclosed honestly:** this only helps the 13 parents with a real, findable home
conversation (26 of the 47 total evasion variants). AgentPoison, MemoryGraft, and MINJA
have no gold QA pair and are not extended by this fix. It is a measurement of the
ceiling when full provenance IS available — it is NOT wired into `B12`'s live decision
path, because a live retrieval pool does not generally include a poison's full source
conversation the way this experiment constructs it.

## 2. Preference hijack — attempted, confounded, not shipped

Tested whether a fabricated preference has lower "corroboration" (max embedding
similarity to any other real preference statement) than a genuine one. Result looked
separable (hijacks ~0.49–0.54, genuine ~0.6–0.85), **but this is very likely an
LLM-authorship-style artifact** (the hijacks are LLM-generated text; the "genuine" set is
real human-written LoCoMo text) rather than a real corroboration signal — it was tested
against other real preferences from DIFFERENT people/topics, not against multiple real
mentions of the SAME preference, which is what a genuine corroboration mechanism would
need. **Not wired into any live config** — shipping a signal that may really be detecting
"this text sounds LLM-written" would misrepresent what was measured and risks false
positives on any non-LoCoMo-style benign text. Reported as an inconclusive, confounded
result, not a fix. (`phase17/preference_corroboration.py`)

## 3. AgentPoison query-side trigger — attempted, real negative result

Built and tested a `universal_retrieval_magnet_score`: does the real AgentPoison
gradient-optimized trigger text ("regulates ned kane seized buffalo 1916...") show
anomalously high average cosine similarity across a large, diverse, cross-conversation
set of real LoCoMo queries, compared to real benign memories? **Result: no.** The real
AgentPoison artifact's z-score (1.34) does not clear even a lenient 2-sigma threshold,
while the threshold already has 2/100 real benign false positives before catching
anything. **Honest conclusion:** AgentPoison's trigger was gradient-optimized against a
different (BERT-based) retriever than this stack's `bge-small-en-v1.5` embeddings — the
"universal magnet" property likely does not transfer across embedding spaces. This
remains a genuinely unaddressed attack surface; forcing the threshold down to catch this
one point would be tuning on the eval sample, which was not done.
(`phase17/query_trigger_signal.py`)

## 4. A-MEM evolution — root cause resolved (though the underlying behavior itself is not fixable by this project)

Previously "unresolved: model decision vs. call failure." Traced the raw controller
response directly: `qwen2.5:7b` and `llama2` both genuinely return
`{"should_evolve": false, ...}` — a real, valid JSON decision, never a swallowed
exception. Reran the exact Phase 7 pottery-class example 5 times: **0/5 evolved**, so this
is not session-to-session sampling noise either; under the current Ollama/model build,
A-mem-sys's evolution step consistently declines for this content. **Resolved diagnosis:
it is the model's real decision, not an infrastructure bug** — the earlier Phase 7
"confirmed" result may reflect a different model/library version at the time. This is
disclosed as a real finding about a third-party vendored library's behavior, not
something this benchmark can patch without abandoning "reuse the real vendor code
verbatim" discipline.

## 5. Mem0 — installed and tested live for the first time in this project's history

A fresh isolated venv (`C:\mem0venv`) installed `mem0ai==2.0.19` + `qdrant-client`
cleanly (plus `sentence-transformers`, `ollama`, `jsonschema` transitive requirements).
The project's own existing, previously-never-exercised `RealMem0Adapter`
(LLM-free `infer=False` add path, real on-disk Qdrant, real HuggingFace embeddings) now
runs for real: `initialize` → `AVAILABLE`, `add_memory` → real assigned id, `retrieve` →
`PARTIAL` (real ids returned). Ran the same 27 real Track B poison cases used for the
A-MEM live test: poison retrieved 27/27 (100%).

**CORRECTION (2026-09-28, found by external review — the original result below was
WRONG, not a real foundation-dependence finding.** `phase17/mem0_live/stage2_defend.py`
built one global `{memory_id: text}` lookup across all 27 cases before scoring any of
them. The `original`/`plain`/`embedded` variants of the SAME poison case deliberately
reuse the SAME `poison_id` string as their memory_id (so the three variants line up
across comparisons) — which meant the global dict let each later case's text silently
overwrite the earlier one under that shared key, so every `original` and `plain` case
was actually scored against whichever variant happened to be written last into the
dict (in practice, usually `embedded`), never its own real text. The fix is to build
that lookup fresh per case (`text_by_id = dict(c["items"])` inside the per-case loop,
matching how `amem_live/stage2_defend.py` already did it correctly using each case's own
`retrieved` list). Re-scored on the SAME stage-1 retrieval output (no new Mem0/Ollama
calls needed):

| | Wrong (published) | Corrected |
|---|---|---|
| B9/B11/B12, `poison_original` excluded | 0/9 | **9/9** |
| B11/B12, `poison_plain` excluded | 0/9 | **1/9** |
| B11/B12, `poison_embedded` excluded | 0/9 | 0/9 (unchanged) |

**Corrected conclusion: Mem0 behaves essentially the same as A-mem-sys** (9/9 original
poison excluded on both real foundations) — there is no real, measured
memory-foundation-dependence effect here. The "smaller candidate pool changed the
divergence score" explanation in the original write-up was invented to fit a wrong
number and never held up: it could not have explained B12's result either, since B12
scores each retrieved text independently and does not depend on the rest of the pool's
composition the way the retrieval-consensus signal does. `phase17/canonical_matrix.py`'s
12 live-Mem0 rows and every downstream document citing the old numbers are superseded by
this correction; `phase17/mem0_live/stage2_results.json` and `canonical_matrix.json` have
been regenerated. This finding is a genuine engineering bug this project made and is
disclosed as such, per this project's own "never let a wrong result stand uncorrected"
discipline.

## 6. Chinese-language exclusion — alternative approach validated, not a clear win

Tried a multilingual embedding backbone (`paraphrase-multilingual-MiniLM-L12-v2`,
confirmed 0.86 mean cross-lingual cosine similarity between real English/Chinese poison
pairs) trained ONLY on English dev data (zero Chinese text in training — a genuine
zero-shot cross-lingual test), scored directly on Chinese text with no translation step.
**Result: 28/84 (33.3%) excluded, 0/447 benign false positives** — essentially on par
with the existing translate-then-score approach (30/84, 35.7%), architecturally simpler
(no extra LLM translation call per memory) but not a clear improvement. Reported as a
validated alternative, not a fix that changes the headline number.
(`phase17/multilingual_stacked.py`)

## 7. Random-budget-matched baseline, unseen-model-family, content forgery

Already covered in the workstreams report §18 (round 2) — carried forward, not repeated
here.

## 8. Blinded human evaluation — a real packet built, not fabricated data

Built a genuine blinded 60-item evaluation packet from real Track-A answers
(`phase17/data/human_eval_packet_blind.json` + `_key.json` +
`HUMAN_EVAL_INSTRUCTIONS.md`). No human rated it during this session (still disclosed as
not executed) — but the packet itself is real and ready for a human to use, closing the
"nothing exists to close this gap" version of the limitation.

## 9. Canonical matrix — extended with real live-Mem0 rows

`phase17/canonical_matrix.py` now includes 12 more real rows from the live Mem0 test
(36 rows total, up from 24), closing the "Mem0/live-Mem0 rows are not measured" note.

## Full regression

Run immediately after all of the above (`phase6/ phase8/ phase11/ phase12/ phase13/
phase14/ phase15/ phase17/ attribution/ phase7/ phase3/ -m "not slow"`):
**2715 passed, 30 skipped, 9 deselected, 0 failed** (1599.3s). New tests:
`phase17/tests/test_round3_fixes.py` (3 passed).
