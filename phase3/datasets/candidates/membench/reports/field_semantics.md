# MemBench Field Semantics

Derived from direct inspection of the bundled `MemData/*.json` records (full-corpus scan) and
the benchmark harness source code (`benchmark/env/Membenenv.py`, `benchmark/MembenchAgent.py`,
`benchmark/load_test_data.py`). Where the source does not make a property unambiguous, it is
marked `UNKNOWN`.

## Top-level record shape

Each `MemData/{variant}/{category}.json` file is a JSON object keyed by **scenario** name
(e.g. `roles`, `events`, `movie`, `food`, `book`, `items`, `places`, `hybrid`, `multi_agent`)
mapping to a **list of records**. Each record:

| Field | Meaning | Required | Nullable | Evaluator-visible only? | Stability | ID vs. label | Source-grounded vs. generated |
|---|---|---|---|---|---|---|---|
| `tid` | Trajectory/task id, integer, unique within (variant, category, scenario) | yes (100%) | no | no (agent-visible: identifies the task instance, not a leak) | stable, confirmed unique per scan | ID | source-provided |
| `message_list` | The full conversation the agent is meant to remember, in one of three observed shapes (see below) | yes (100%) | no | no -- this is the agent-visible transcript itself | stable | content | source-generated (LLM-synthesized dialogue per README/paper) |
| `QA` | The evaluation question bundle for this record | yes (100%) | no | mixed (see sub-fields) | stable | -- | source-generated |
| `QA.qid` | Question id | yes (100%) | no | agent-visible (harmless label) | **NOT reliably unique** -- duplicates in ~499/500 records per scenario in nearly every file (see raw_inventory.md); do not use alone as a key | label, not a safe ID | source-provided |
| `QA.question` | The natural-language question posed to the agent at the end of the trajectory | yes (100%) | no | agent-visible | stable | content | source-generated |
| `QA.time` | The "current time" at which the question is asked (used in the harness's prompt template, e.g. `Membenenv.py` / `MembenchAgent.py` INSTRUCTION templates) | yes (100%) | no | agent-visible | stable | content | source-generated |
| `QA.choices` | Four multiple-choice options, dict with keys `A`/`B`/`C`/`D` | yes (100%) | no | agent-visible (the agent must see the choices to answer) | stable | content | source-generated |
| `QA.answer` | Free-text canonical answer string | yes (100%, 0 missing across 26,637 records) | no | **evaluator-only** | stable | content (gold) | source-generated |
| `QA.ground_truth` | The correct choice letter (A/B/C/D) | yes (100%, 0 missing) | no | **evaluator-only** | stable | label (gold) | source-generated |
| `QA.target_step_id` | List of `[session_index, turn_index]` (or, in flat-turn categories, `[turn_index]`) pairs identifying the transcript location(s) that ground the answer | 99.985% present (26,633/26,637; see raw_inventory.md for the 4 exceptions) | yes, in 4 records | **evaluator-only** -- this is the gold evidence pointer used by the harness's own `get_recall()` function (`Membenenv.py`) to score retrieval | stable where present | evidence pointer (gold) | source-provided (hand-annotated by generation pipeline, not inferred by us) |

## `message_list` turn shapes (three observed variants)

The container itself is either:
- **nested**: a list of sessions, each a list of turn dicts (most FirstAgent categories, and
  all ThirdAgent categories that use dialogue -- actually ThirdAgent uses the flat shape, see
  below); or
- **flat**: a single list of turn dicts with no session grouping at all (all ThirdAgent
  categories -- the source provides no explicit session boundary for the Observation variant).

Turn-level field sets observed (three shapes, all normalized into one common turn record --
see `normalized/`):

1. **FirstAgent dialogue turn** (`simple`, `noisy`, `knowledge_update`, `aggregative`,
   `comparative`, `conditional`, `highlevel`, `post_processing`, `RecMultiSession`):
   `sid` (turn id within session), `user_message`, `assistant_message`, `time`, `place`, and
   occasionally `rel`/`attr`/`value` (a source-provided fact triple -- relation/attribute/value
   -- marking the specific fact the turn establishes; present only on the turn(s) that carry
   the answer-bearing information, `NOT_PROVIDED_BY_SOURCE` elsewhere).
2. **FirstAgent recommendation/multi-session turn** (`highlevel_rec`, `lowlevel_rec`,
   `RecMultiSession`'s `multi_agent` scenario): `mid` (turn id), `user`, `assistant`, `time`,
   `place`. Same semantic role as shape 1, different key names in the source.
3. **ThirdAgent observation turn** (all `ThirdAgent/*` categories): `mid`, `message` (a single
   narrated statement, no dialogue split -- consistent with "Observation" framing: the agent
   witnesses information about a third party rather than participating in a conversation),
   `time`, `place`, and occasionally `rel`/`attr`/`value` as in shape 1.

`rel`/`attr`/`value`: these appear **inline in the transcript itself** (i.e. on a turn the
agent would see), not in a separate evaluator-only structure. They were treated as
agent-visible in normalization on that basis, distinct from the `QA.answer` /
`QA.ground_truth` / `QA.target_step_id` fields which never appear in the transcript and are
only present in the `QA` sub-object.

## `graphs.json` (top-level, outside `MemData/`)

A separate 500-entry file of synthetic user-profile "graphs" (`gid`, `user_profile` with
name/age/height/birthday/hometown/occupation/company/contact info, plus synthetic-looking
identifiers such as `ssn`, `passport_number`, `bank_account`, `driver_license`,
`highlevel_preference`). This is the **generation seed data** used to build the `MemData`
conversations (per `DialogueGeneration/*.py`, which imports `TimeClock`/`rewrite_message`/etc.
utilities not bundled in this repo -- the `utils` module they `import` is not present at the
pinned commit, so the generation pipeline cannot be re-run from this repo alone; `UNKNOWN`
whether it lives in a separate, unlinked module).

**Content-handling note:** the SSN/passport/bank-account/driver-license-shaped strings in
`graphs.json` are **synthetic placeholders used to seed fictional dialogue content**, not real
individuals' data, consistent with the file's role as a generation seed for a research
benchmark. This is stated based on context (structure, benchmark purpose, absence of any real-
world corroboration) -- it is not independently verifiable as fictional beyond that, so treat
this file with the same caution as any dataset containing PII-shaped strings.

## `MakeNoise/NoiseMeta/*.json`

`messagenoise_new.json` and `sessionnoise_new.json`: pools of unrelated, real-world-topic
filler dialogue (`nid`, `noise_message`: list of `{sid, user, assistant}` turns) used by
`MakeNoiseMessage`/`MakeNoiseSession` (see `benchmark/load_test_data.py`) to interleave
distractor content into a trajectory, extending its length for the "noisy" evaluation
condition. Distinct from the pre-built `noisy.json` category files in `MemData/`, which are
the paper's own already-noise-injected split.

## Evaluator/agent boundary applied

Per `phase3/evaluation/contracts/boundary.py`'s `FORBIDDEN_KEYS` convention, the following
MemBench-native fields were treated as **evaluator-only** and excluded from
`agent_visible_context` in every normalized record: `QA.answer`, `QA.ground_truth`,
`QA.target_step_id`. Everything else in the record (`message_list` transcript content,
`QA.question`, `QA.time`, `QA.choices`) was treated as agent-visible. All 275 normalized
sample records were validated against `boundary.validate_agent_visible()` with zero
violations (see `phase3/evaluation/tests/test_candidate_membench.py`).
