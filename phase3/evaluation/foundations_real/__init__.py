"""Phase 3.2-H.4 (Dataset + Memory Foundation Conformance) -- real (non-mock) memory
foundation adapters.

WHY A NEW SIBLING PACKAGE, NOT `phase3/evaluation/foundations/real/`
--------------------------------------------------------------------------------
The task brief for this stage suggested a path shaped like
`phase3/evaluation/foundations/real/mem0_adapter.py`. This package deliberately does NOT
live there. Reason, found by inspection before writing a single adapter line:

`phase3/evaluation/tests/test_foundation_architecture_h3.py` (a PROTECTED, existing test
file -- never to be modified, per this stage's own absolute protection rules) contains two
hard assertions, in `TestMockVsRealConformance`:

1. `test_trace_artifact_rejects_any_other_conformance_tag` -- constructs
   `trace.build_trace(..., conformance_tag="REAL_FOUNDATION_CONFORMANCE")` and asserts it
   RAISES `ValueError`. `foundations/trace.py`'s `FoundationTraceArtifact.__post_init__`
   hard-codes `conformance_tag` to the single literal value `"MOCK_CONFORMANCE"` --
   deliberately, per H.3's own module docstring, because no real foundation ran in H.3.
2. `test_no_function_in_foundations_package_can_return_real_conformance` -- greps EVERY
   `.py` file under `phase3/evaluation/foundations/` (recursively, `rglob("*.py")`) for a
   live `conformance_tag = "REAL_FOUNDATION_CONFORMANCE"` assignment pattern and asserts
   zero matches anywhere in that package.

Both are correct and appropriate for H.3's scope, and both are permanently protected --
this stage cannot touch either. Widening `trace.py`'s `conformance_tag` vocabulary (the
"natural" fix for a stage whose entire point is genuine real-foundation conformance) would
directly break assertion (1); and *any* new file placed under `foundations/` that
legitimately needs to record `conformance_tag="REAL_FOUNDATION_CONFORMANCE"` for a real,
non-fabricated result would trip assertion (2) regardless of which class produced it --
that check is a blanket, path-scoped ban, not a `FoundationTraceArtifact`-specific one.

The honest resolution, not a workaround: H.3's `foundations/` package is, by its own
explicit and correct design, a MOCK-ONLY architecture package -- "no real foundation runs
here" is exactly the invariant those two tests exist to enforce, forever, regardless of
what a later stage achieves elsewhere. H.4's real adapters are a genuinely NEW, ADDITIVE
kind of thing this codebase did not have before -- they belong in their own package, not
squeezed into one whose own tests declare real conformance out of scope. `foundations_real`
is a sibling of `foundations`, not a subpackage of it: it implements the SAME
`MemoryFoundationAdapter` interface (`foundations/adapter.py`, imported and used verbatim,
never re-defined here) but produces its own `RealConformanceRecord` trace shape (see
`conformance_record.py`), NOT a `FoundationTraceArtifact`, because that shape's
`conformance_tag` vocabulary is deliberately, permanently restricted to `MOCK_CONFORMANCE`.

WHAT LIVES HERE
--------------------------------------------------------------------------------
- `conformance_record.py`: `RealConformanceRecord`, the H.4 analogue of
  `FoundationTraceArtifact`, permitting exactly the tag vocabulary this stage needs
  (`REAL_FOUNDATION_CONFORMANCE`, `MODEL_DEPENDENT`, `ENVIRONMENT_LIMITATION`, `DEFERRED`,
  `NOT_ATTEMPTED`) -- never `MOCK_CONFORMANCE` (that remains `foundations/`'s own word for
  its own, different thing).
- `environment.py`: the pinned, resolved isolated-venv package manifest this stage's real
  conformance claims are grounded in (no secret/credential values recorded, per
  `foundations.fingerprinting.reject_secrets`' same discipline, reused verbatim here).
- `mem0_real_adapter.py`, `graphiti_real_adapter.py`, `amem_real_adapter.py`,
  `letta_real_adapter.py`: one `MemoryFoundationAdapter` implementation per foundation.
  Every method either (a) genuinely calls the real installed library (recorded
  `REAL_FOUNDATION_CONFORMANCE`), or (b) is honestly reported `MODEL_DEPENDENT` /
  `ENVIRONMENT_LIMITATION` / `DEFERRED` with a specific, falsifiable reason -- never a
  fabricated pass.

DEPENDENCY ISOLATION (mandatory, per this stage's own instructions)
--------------------------------------------------------------------------------
None of `mem0`, `graphiti_core`, `sentence_transformers`, `chromadb`, `letta_client`, or any
other real-foundation package is installed in the environment `python -m pytest
phase3/evaluation/tests/ -q` runs under -- they live ONLY in an isolated virtualenv created
for this stage (`C:\\h4venv`, deliberately placed at a short path OUTSIDE the repo tree; an
earlier attempt at a venv nested deep under this session's scratchpad directory hit
Windows' 260-character MAX_PATH limit on torch's bundled C++ headers -- a real, mundane
environment constraint, not a library defect). Every adapter module in this package
therefore imports its real library lazily, inside a function, guarded by `try/except
ImportError` -- so `test_foundation_conformance_h4.py` collects and runs cleanly (with
every real-library-dependent assertion self-skipping to a `NOT_ATTEMPTED`/environment-
limitation report) under the MAIN repo environment the 833-test baseline runs in, while
still being genuinely, actually exercised when run under `C:\\h4venv`'s interpreter -- which
is how every real result this stage reports was actually produced. See
`PHASE3_2_H4_DATASET_FOUNDATION_CONFORMANCE.md` for the full installed-package manifest,
versions, and the exact commands used.
"""

from __future__ import annotations

__all__: list = []
