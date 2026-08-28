# Field Semantics — MemoryArena (HuggingFace `ZexueHe/memoryarena`)

Full-scan basis for every field below: all 701 records across the 5 configs (see
`reports/raw_inventory.md`). No sampling was used.

## Common fields (all 5 configs)

### `id` (int)
- **Meaning:** identifier for one interdependent-multi-subtask "agentic task chain"
  record within its config.
- **Required:** yes, present in 701/701 records.
- **Nullable:** no (never observed null).
- **Evaluator-visible or agent-visible:** evaluator-only in the MAMBench sense — it is a
  bookkeeping/lookup key, not agent-facing content, and carries no gold-answer
  information itself, so it is safe to expose to an agent as a task identifier (it is
  not a "gold_*" or "evaluation_*" key under `phase3/evaluation/contracts/boundary.py`'s
  `FORBIDDEN_KEYS`), but this candidate profile does not build an actual
  `AgentVisibleContext` payload (no agent execution performed), so this is a judgment
  call for future integration, not a tested fact.
- **Stability:** stable within a config's `data.jsonl` file as downloaded; NOT
  necessarily stable across HF dataset revisions (no revision-diffing was performed).
- **ID vs. label:** ID (unique per config; see raw_inventory.md duplicate counts).
- **Source-grounded vs. generated:** source-grounded (assigned by the dataset authors,
  not invented during this normalization).

### `questions` (list of str)
- **Meaning:** ordered list of subtask instructions/prompts within the task chain. In
  `bundled_shopping` these are full agent system-prompt-style instructions (see
  `raw_inventory.md`); in `progressive_search` these are natural-language clue questions;
  in `group_travel_planner` these are "I am <name>, joining <base_person> ..." trip
  requests; in `formal_reasoning_*` these are the actual math/physics problem statements.
- **Required:** yes, present and non-empty-list in 701/701 records.
- **Nullable:** no element is null or empty string anywhere (full scan, 4850 elements).
- **Evaluator-visible or agent-visible:** AGENT-VISIBLE — this is literally the prompt
  content the task poses to the agent. Contains no gold-answer leakage on inspection.
- **Stability:** content is static task text; stable as long as the source file is
  unchanged.
- **ID vs. label:** label/content (free text), not an identifier.
- **Source-grounded vs. generated:** source-grounded.

### `answers` (list; element TYPE VARIES BY CONFIG — see per-config note below)
- **Meaning:** gold answer for the corresponding `questions[i]` subtask.
- **Required:** yes, present and length-matched to `questions` in 701/701 records.
- **Nullable:** no element null/empty anywhere (full scan).
- **Evaluator-visible or agent-visible:** EVALUATOR-ONLY (gold answer) — must never be
  placed in an agent-visible payload; maps directly onto `boundary.py`'s
  `gold_answer`/`gold_answers` forbidden-key family in spirit (the literal key name here
  is `answers`, not `gold_answers`, so any future adapter building an
  `AgentVisibleContext` from this data MUST rename/exclude this field explicitly — this
  profile flags that as a required adapter step, it does not perform the renaming
  itself).
- **Stability:** static gold content.
- **ID vs. label:** content/label.
- **Source-grounded vs. generated:** source-grounded.
- **Element type per config (full scan of all `answers` elements, corrected from an
  earlier draft of this report which had checked only `progressive_search` before
  generalizing — the actual per-config breakdown is):**
  - `bundled_shopping`: all 900 elements are **dict** (`{"target_asin": ..., "attributes":
    [...]}`) — this is the shape the HF README's `progressive_search` example actually
    illustrates, i.e. the README's illustrative example is mislabeled onto the wrong
    config, not merely "different from the actual data" as an earlier draft of this
    report stated. The real shape belongs to `bundled_shopping`.
  - `progressive_search`: all 1641 elements are **str** (plain text answers) — contrary
    to the README's dict-shaped illustrative example for this config.
  - `group_travel_planner`: all 1869 elements are **list** (each a list of per-day plan
    dicts, matching the `base_person.daily_plans` shape).
  - `formal_reasoning_math`: all 354 elements are **str**.
  - `formal_reasoning_phys`: all 86 elements are **str**.
  - This normalization preserves each answer's native type verbatim (no coercion to a
    single "answer string" shape across configs) — see `normalized/normalize.py`, which
    stores `answer` as whatever JSON value the source provided, dict/list/str alike.

## Config-specific fields

### `category` (str) — `bundled_shopping` only
- **Meaning:** product category/item slot label (e.g. `baking_item_3`).
- **Required:** yes, 150/150.
- **Evaluator-visible or agent-visible:** could be agent-visible (it's descriptive
  metadata, not a gold label) but this profile does not assert that judgment as tested.
- **Stability:** stable, one-to-one with `id`.
- **ID vs. label:** label (descriptive), not a unique identifier on its own (though it
  happens to be unique per record in this dataset — a coincidence of the fixed 5x30
  design, not a general guarantee).
- **Source-grounded:** yes.

### `paper_name` (str) — `formal_reasoning_math`/`formal_reasoning_phys` only
- **Meaning:** identifier of the source academic paper the math/physics problems were
  derived from (e.g. an arXiv-style ID like `2503.19064`, or a `_part_N` suffix when one
  paper's content was split across multiple records).
- **Required:** yes, 40/40 (math) and 20/20 (phys).
- **Evaluator-visible or agent-visible:** likely agent-safe (descriptive provenance, not
  a gold answer) but untested.
- **Stability:** stable per record.
- **ID vs. label:** partially an ID (groups records by source paper) but not unique per
  record (e.g. `_part_2` suffix indicates multiple records share a base paper).
- **Source-grounded:** yes — this is the closest thing to a `source_record_id`/lineage
  pointer this dataset provides, and it is preserved verbatim in the normalized view's
  `source_task_id`-adjacent field (see `normalized/README.md`).

### `backgrounds` (list of str) — `formal_reasoning_math`/`formal_reasoning_phys` only
- **Meaning:** per-subtask necessary definitions/context (mathematical/physical setup)
  the agent needs to solve `questions[i]`.
- **Required:** yes, 40/40 and 20/20; length always matches `questions`' length (0
  mismatches, full scan).
- **Evaluator-visible or agent-visible:** AGENT-VISIBLE — this is legitimate context the
  agent needs to attempt the subtask, analogous to `GOLD_EVIDENCE`-condition content in
  the MAMBench contract, not a gold answer.
- **Nullable:** no null/empty entries observed.
- **Source-grounded:** yes.

### `base_person` (dict: `name`, `query`, `daily_plans`) — `group_travel_planner` only
- **Meaning:** the anchor traveler's profile and full itinerary, which all subsequent
  `questions[i]` ("joiner" requests) must remain consistent with.
- **Required:** yes, 270/270, with all three sub-keys present in every record (full scan).
- **Evaluator-visible or agent-visible:** AGENT-VISIBLE for `name`/`query` (the request
  text). `daily_plans` is ambiguous: it could double as gold-reference content for
  evaluating a joiner's plan consistency, similar to how `answers` functions elsewhere —
  this profile flags `daily_plans` as requiring an explicit agent-vs-evaluator policy
  decision before any adapter is built, rather than asserting one itself.
- **Nullable:** no.
- **Source-grounded:** yes.

## Fields this dataset does NOT provide (recorded as `NOT_PROVIDED_BY_SOURCE`, full-scan
confirmed absent — not inferred)

- `memory_id` / any per-memory-unit stable identifier — absent in all 701 records
  (there is no separate "memory record" layer at all in this dataset; see
  `raw_inventory.md`).
- `session_id` / `conversation_id` — absent in all 701 records. Subtask ordering is
  positional (list index) only, not an explicit session/turn field.
- `timestamp` / any temporal field — absent in all 701 records.
- `evidence_memory_ids` / any explicit gold-evidence-ID pointer distinct from the answer
  text itself — absent. `backgrounds` (formal_reasoning only) is the closest analogue,
  but it is *context text*, not an ID pointing at a separately-identified memory unit.
- `parent_ids` / `equivalent_to` / `conflicts_with` / `superseded_by` — absent in all 701
  records (checked identically to the LoCoMo profile's whole-file-grep method, applied
  here to every file since all are small enough for a full scan rather than a grep
  sample).
- Explicit machine-readable subtask-interdependency edges (e.g. `depends_on: [...]`) —
  absent; interdependency is structural/positional and textual only (see
  `raw_inventory.md`'s "Task interdependency structure" section).
- Tool-call / environment-observation / agent-turn logs — absent from the JSONL task
  data; would only exist if the repo's `agent`/`env`/`memory` code were actually executed
  against these tasks, which this stage does not do.

## Ambiguous / `UNKNOWN` fields

- Whether `id` is stable across future HuggingFace dataset revisions: **UNKNOWN** — only
  one snapshot (commit `da1a37c8b19280e18627ca01cf370195a5e1d92e`) was inspected; no
  revision history was diffed.
- Whether `progressive_search`'s README-illustrative dict-shaped answer format
  (`target_asin`/`attributes`) exists in some *other*, non-downloaded revision or split of
  the dataset: **UNKNOWN** — only the `test` split of each config (the only split the
  dataset card advertises) was downloaded and inspected.
- Whether `group_travel_planner.base_person.daily_plans` should be treated as
  agent-visible context or evaluator-only gold reference: **UNKNOWN / policy decision
  required**, see above.
