# Active Clean Baseline Clarification

Status: **NOT FROZEN** — a clarifying cross-reference, not a new decision. Written to
close a naming ambiguity the Phase 3 completion audit found: `clean_agent_memory_v1`
exists in this repository, but not where an active-tree search would expect it.

## 1. The ambiguity

`clean_agent_memory_v1` (manifest, config, reports) exists **only** under
`phase3_reference/clean_agent_v1/`. Per
[PHASE3_RESTART_BOUNDARY.md §3](PHASE3_RESTART_BOUNDARY.md) (frozen): `phase3_reference/`
"contains the previous Phase 3 attempt in its entirety... is read-only reference
material. Its results are historical evidence, not validated design." That document
already establishes this boundary; what it does not do is name the active-tree
equivalent — which is what caused the audit's ambiguity.

**`phase3_reference/` is also entirely untracked by git** — confirmed during the audit
(`git ls-files phase3_reference` returns zero results). Its provenance cannot be verified
the way every file under the active `phase3/` tree can (single-commit history, no
post-hoc tampering, per the audit's own git-log check on the real 3.3-G-formal result
files). Do not treat anything under `phase3_reference/`, including
`clean_agent_memory_v1`, as validated evidence of anything about the current system.

## 2. What the active tree actually has instead

There is no single artifact in the active `phase3/` tree literally named
`clean_agent_memory_v1`. The equivalent, active, validated material is split across two
things that together serve the same role:

- **The reference clean agent implementation**: `phase3/evaluation/agent_runtime/
  runner.py::run_agent_task()` — self-described in its own module docstring as "the
  canonical clean-baseline agent loop." This is the de facto reference agent; no file is
  separately named "reference_agent.py" or similar.
- **The frozen clean baseline evidence**: the 3.3-G-formal campaign
  (`campaign_id: "3.3-G-formal-2026-09-01"`, `sampling_seed: 33005`), manifest at
  `phase3/experiments/manifests/campaign_3_3g_manifest.json`, real result files at
  `phase3/experiments/results/campaign_3_3g_formal_*.json` (multi-megabyte, real
  task-level records, confirmed by direct read during the audit), analysis at
  `phase3/experiments/results/campaign_3_3g_formal_analysis.json`. Committed in a single
  commit (`4c059df "Phase G/G.1"`), never touched again — confirmed via `git log --stat`
  during the audit.

## 3. What this means going forward

- Do not search for or reference `clean_agent_memory_v1` as if it were the active
  system's own artifact — it is historical material from a superseded attempt.
- When "the clean baseline" needs to be cited, cite the 3.3-G-formal campaign manifest +
  result files (above), not anything under `phase3_reference/`.
- If a future stage wants a single, explicitly-named "v1" artifact in the active tree
  (e.g. for the definitive clean-agent behavioral dataset this audit's own protocol says
  comes after Phase 3 freezes), it should be newly constructed from the frozen 3.3-G-formal
  evidence and named without colliding with the historical `phase3_reference/` name — not
  reuse or relocate the old one, per `PHASE3_RESTART_BOUNDARY.md §3`'s own frozen rule that
  nothing under `phase3_reference/` may be imported/copied into the active implementation
  without being re-derived and re-justified.

## 4. Freeze status

Not a frozen decision — a clarification closing an audit-identified naming ambiguity.
Supersedes no frozen document; cross-references `PHASE3_RESTART_BOUNDARY.md`, which
remains authoritative for the boundary itself.
