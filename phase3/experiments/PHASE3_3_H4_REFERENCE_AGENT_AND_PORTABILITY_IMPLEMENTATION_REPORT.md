# Phase 3.3-H4-REFERENCE-AGENT-AND-PORTABILITY — Implementation Report

Status: **COMPLETE**. Closes two of the audit's smaller `[PARTIAL]` findings: no
dedicated reference-agent file, and a hardcoded `C:\h4venv` path in the one place it was
actually functionally load-bearing (not merely documented in prose).

## 1. Reference agent

New `phase3/evaluation/agent_runtime/reference_agent.py` — a deliberate, thin re-export
of `runner.py::run_agent_task()`, never a second implementation. `run_reference_agent =
run_agent_task` (literal object identity, not a wrapper function, so there is no logic
here that could ever drift from `runner.py`'s own behavior). Tested directly:
`ref.run_reference_agent is runner_mod.run_agent_task`.

This gives "the reference clean agent" one stable, discoverable name, closing the audit's
own finding without duplicating or risking divergence from the actual, already-validated
implementation.

## 2. `C:\h4venv` path portability

Repo-wide grep found the overwhelming majority of `h4venv` mentions are documentation/
comments describing the real environment (correct, left unchanged) or the already-
centralized `environment.py::VENV_PATH` constant (a deliberate, frozen historical record
of Phase 3.2-H.4's own real-conformance environment — correctly NOT made dynamically
overridable, since blurring that record's historical-truth purpose would be worse than
the portability gain).

**The one genuinely hardcoded, functionally load-bearing path** was
`amem_real_adapter.py`'s `repo_root = r"C:\h4venv\a-mem-sys-repo"` — a second, independent
literal duplicating `VENV_PATH` rather than deriving from it. Fixed: now
`os.environ.get("MAMBENCH_H4VENV_PATH", VENV_PATH)`, joined with `"a-mem-sys-repo"` —
derives from the single documented source of truth, defaults to the exact same value as
before (zero behavior change for every existing real run), and is overridable via one
environment variable for a checkout on a different machine.

**Verified both directions, not just that it compiles**: (1) unmodified behavior —
`initialize()`/`add_memory()`/`inspect_memory()` all still work correctly under
`C:\h4venv`, confirming the default path resolution is unchanged; (2) the override
actually takes effect — setting `MAMBENCH_H4VENV_PATH` to a nonexistent path correctly
makes the adapter report `UNAVAILABLE` (import genuinely fails), proving the environment
variable is really consulted, not merely present and ignored.

## 3. Testing

`test_reference_agent.py` (2 tests, identity checks). `amem_real_adapter.py`'s existing
conformance test suite re-run under `C:\h4venv`: 10/10 pass, unchanged.

## 4. Regression

Full suite re-run as part of this session's consolidated final pass (see the session's
final full-suite report for the authoritative count).

## 5. What was deliberately not changed

- `environment.py::VENV_PATH` itself — remains a frozen, non-configurable historical
  record, by design (§2 above).
- Every prose/comment mention of `C:\h4venv` across `pilot_*.py`, `identity.py`,
  `provider.py`, etc. — these describe the real environment accurately; changing them to
  reference a variable would make the documentation less concrete for a reader trying to
  understand what was actually run, for no functional benefit (none of them contain a
  hardcoded, load-bearing path literal — confirmed by the same repo-wide grep).

## 6. Compatibility and freeze status

One new file (`reference_agent.py`, pure re-export), one small, additive fix to
`amem_real_adapter.py` (default-preserving). Not a frozen decision.
