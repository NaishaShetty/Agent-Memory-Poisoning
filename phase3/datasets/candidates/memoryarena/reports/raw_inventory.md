# Raw Inventory — MemoryArena

**Inspection method: full scan, not sampling.** All five HuggingFace configs
(`bundled_shopping`, `progressive_search`, `group_travel_planner`, `formal_reasoning_math`,
`formal_reasoning_phys`) are small enough (20–270 records each, 701 total) that every line
of every file was parsed and checked programmatically — no prefix sampling was used
anywhere in this inventory, unlike the 500/300-line samples used for LoCoMo's much larger
files. This is stated explicitly because the task brief requires saying exactly how much
was scanned.

## Record counts (task-chain level)

| Config | Records (task chains) | Total subtasks (sum of `questions` lengths) | Subtasks per record (min/max/avg) |
|---|---|---|---|
| bundled_shopping | 150 | 900 | 6 / 6 / 6.0 |
| formal_reasoning_math | 40 | 354 | 2 / 16 / 8.85 |
| formal_reasoning_phys | 20 | 86 | 2 / 12 / 4.3 |
| group_travel_planner | 270 | 1869 | 5 / 8 / 6.92 |
| progressive_search | 221 | 1641 | 4 / 16 / 7.43 |
| **Total** | **701** | **4850** | — |

There is no separate "memory record" file/layer anywhere in this dataset (see
`reports/field_semantics.md`) — the closest analogue to a per-turn memory unit is one
**subtask** (one `questions[i]`/`answers[i]` pair) within a task chain, since the paper's
premise is that an agent must remember earlier subtask context/answers to solve later
subtasks in the same chain. There are no explicit memory IDs, session IDs, or timestamps
anywhere in the HF dataset (see below).

## Task interdependency structure

Every record in every config is, by construction, a **chain of interdependent subtasks**
sharing one JSON object (one `id`). The nature of the interdependency differs by config:

- **bundled_shopping**: subtasks are literally sequenced — the record's global rules
  state "You need to buy products on the order of the steps (i.e., Product 1 first, then
  Product 2, and so on)" (verbatim from `questions[0]` of record id=0). Each subtask is a
  purchase step for a "bundle" whose earlier choices constrain later ones (e.g. budget
  remaining, compatibility).
- **progressive_search**: subtasks are a chain of narrowing search clues about the same
  underlying entity/topic (e.g. "which individual stated X in a 2020 interview" ->
  "which individual, who graduated from Y, ..."), each building on facts established
  by earlier subtasks/answers within the same record.
- **group_travel_planner**: one `base_person` establishes a base itinerary (`daily_plans`);
  each subsequent `questions[i]` is a new person "joining" that base trip, and its
  `answers[i]` is a full derived itinerary that must remain consistent with the
  established base plan — i.e. later subtasks structurally depend on the base_person
  content plus (in a real multi-agent run) whatever earlier joiners' plans were already
  produced.
- **formal_reasoning_math / formal_reasoning_phys**: each record is anchored to one
  source `paper_name` (e.g. `"2503.19064"`, or a `_part_N` suffix for a paper split across
  multiple records); each subtask has its own `backgrounds[i]` (necessary
  definitions/context) but subtasks within a record build on the same paper's shared
  formal framework, and later subtasks frequently reference results established in
  earlier ones (e.g. record id=0 subtask 2 of formal_reasoning_math builds on the
  homeomorphism established in subtask 1 — see `reports/field_semantics.md` for the
  verbatim excerpt).

No config provides an explicit machine-readable edge list (e.g. `depends_on: [subtask_ids]`)
— the interdependency is structural (position within the shared `questions`/`answers`
list of one record) and textual (later subtask text refers back to earlier context), not
a separate graph field. This is recorded honestly as `NOT_PROVIDED_BY_SOURCE` for
"explicit interdependency edges" in `reports/field_semantics.md` and
`profile/memoryarena_profile.json`, while "task chain grouping via shared record id" is
recorded as `AVAILABLE`.

## Environment/tool/agentic fields

None of the five HF dataset configs carry per-subtask tool-call, environment-observation,
or role-turn fields — the JSONL data is the **task specification and gold answer**, not an
agent trajectory log. Trajectories (with tool calls, environment observations, and
agent/environment turns) would be produced only by *running* the code in `agent/`, `env/`,
and `memory/` against these tasks — which this candidate-preparation stage does not do
(no execution, per the task's absolute rules). The repo's environments (`env_systems/`)
do define environment-specific state (e.g. `travel_planner_env/database/` CSVs of
flights/hotels/restaurants/attractions used by the travel-planner tool implementations),
but this is environment *reference data*, not a per-task-record field in the JSONL files.

## Null / empty / missing-field counts (full scan, all 701 records)

- `questions`/`answers` length mismatch: **0 / 701** records (every record's `answers`
  list is exactly as long as its `questions` list, in every config).
- Null entries within any `questions` or `answers` list: **0** (across all 4850 subtask
  pairs, full scan).
- Empty-string entries within any `questions` or `answers` list: **0** (full scan).
- `answers` list element types differ by config (full scan): `bundled_shopping` = dict
  (900/900, shape `{"target_asin": ..., "attributes": [...]}`), `progressive_search` = str
  (1641/1641), `group_travel_planner` = list of daily-plan dicts (1869/1869),
  `formal_reasoning_math` = str (354/354), `formal_reasoning_phys` = str (86/86). Note:
  the HF README's illustrative "progressive_search" answer example
  (`{"target_asin": ..., "attributes": [...]}`) actually matches the real
  `bundled_shopping` answer shape, not `progressive_search` — the README's example is
  mislabeled onto the wrong config. See `reports/field_semantics.md` for the full
  per-config breakdown. This normalization preserves each config's native answer type
  verbatim rather than coercing to one shape.
- `formal_reasoning_math`/`formal_reasoning_phys`: `backgrounds` is present as a list in
  100% of records (40/40 and 20/20 respectively), and its length always matches
  `questions`'s length (0 mismatches).
- `group_travel_planner`: no record carries a top-level `backgrounds` key at all (0/270) —
  the per-task-brief note that "the travel details of the base person... serve as the
  background information" is corroborated structurally: `base_person` (with `name`,
  `query`, `daily_plans` sub-keys, present in all 270 records) plays that role instead.

## Duplicate-ID counts (full scan)

- `bundled_shopping`: 150/150 unique `id` values (ids 0–149, contiguous).
- `formal_reasoning_math`: 40/40 unique `id` values (ids 0–39, contiguous).
- `formal_reasoning_phys`: 20/20 unique `id` values (ids 0–19, contiguous).
- `group_travel_planner`: 270/270 unique `id` values (ids 1–270, contiguous).
- `progressive_search`: 221/221 unique `id` values (ids 0–220, contiguous).
- **Zero duplicate IDs found in any config, full scan, no sampling.**

## Malformed-record counts

**Zero.** No record in any of the 701 across all five configs failed to parse as JSON, was
missing a required top-level field for its config, or had a `questions`/`answers` length
mismatch. No exclusions were necessary (see `manifests/exclusion_manifest.json`, which is
consequently empty by design, not by omission).

## Task-type distribution

Five distinct task types (one per HF config), corresponding to four *environment families*
in the code repo's `env/env_systems/`:

| Task type | Records | Environment family (repo) |
|---|---|---|
| bundled_shopping | 150 | webshop-style shopping environment |
| progressive_search | 221 | web_search_env (`browsecomp_plus_env.py`) |
| group_travel_planner | 270 | travel_planner_env |
| formal_reasoning_math | 40 | formal_reasoning_env |
| formal_reasoning_phys | 20 | formal_reasoning_env |

`bundled_shopping` additionally carries a fine-grained `category` field (e.g.
`baking_item_0`..`baking_item_29`, `beauty_item_0`..`beauty_item_29`,
`electronics_item_0`..`electronics_item_29`, `grocery_item_0`..`grocery_item_29`,
`home_item_0`..`home_item_29`) — 5 top-level categories x 30 items each = 150, a
one-to-one mapping onto the 150 record ids (full scan confirms this, not a sample).

## Temporal / session-ordering fields

No explicit timestamp or session-ID field exists anywhere in the HF dataset JSONL files.
The only ordering signal is positional: `questions[i]`/`answers[i]` at the same index `i`
within one record are understood (per config README text and the paper's premise) to occur
"in session order" — i.e. subtask 0 happens before subtask 1, etc. — but this ordering is
implicit in list position, not an explicit `session_index`/`timestamp` field. Recorded as
`PARTIAL` (ordering exists and is unambiguous, but is positional/implicit rather than an
explicit labeled field) in `reports/field_semantics.md`.

## Sampling disclosure

None of the above required sampling. Every one of the 701 records and 4850
question/answer pairs, across all five configs, was read and checked in full by a Python
script iterating every line of every `data.jsonl` file (no prefix truncation). This is
explicitly different from, and stronger than, the sample-based inspection method used for
larger datasets like LoCoMo.
