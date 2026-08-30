"""Phase 3.2-H.3 (Memory Foundation Integration Architecture) -- deterministic test-double
("mock") memory-foundation adapters: `MockMem0Adapter`, `MockLettaAdapter`,
`MockGraphitiAdapter`, `MockAMemAdapter`.

================================================================================
FRAMEWORK CONFORMANCE vs. REAL FOUNDATION CONFORMANCE -- THE CRITICAL DISTINCTION
================================================================================
Every one of these four adapters is a deterministic, in-memory, pure-Python TEST DOUBLE.
None of them imports, installs, calls, or in any way depends on the real Mem0/Letta/
Graphiti/A-MEM library, or on any real LLM/embedding/network/vector-database/graph-
database service. Every operation result these adapters produce carries
`conformance_tag="MOCK_CONFORMANCE"` (enforced structurally by
`trace.FoundationTraceArtifact.__post_init__`, which currently accepts ONLY that one
value) -- there is no code path anywhere in this package that can produce
`"REAL_FOUNDATION_CONFORMANCE"`.

**Framework conformance** ("this adapter obeys the `MemoryFoundationAdapter` interface
contract, verified against a deterministic mock") is the ONLY claim established by this
package. **Real foundation conformance** ("the actual Mem0/Letta/Graphiti/A-MEM library,
correctly installed and running, behaves correctly through this adapter") is NOT
established here, is NOT claimed anywhere in this package's code or docstrings, and is
explicitly deferred to a future H.4 stage (see
`PHASE3_2_H3_FRAMEWORK_AND_FOUNDATION_EXTENSION_SPEC.md`'s "H.4 real-conformance plan"
section). `test_foundation_architecture_h3.py` includes a dedicated test that greps this
entire `phase3/evaluation/foundations/` package for the literal string
`"REAL_FOUNDATION_CONFORMANCE"` and asserts it never appears anywhere except inside a
docstring/comment explaining that it is NOT achievable -- i.e. it never appears as a value
any function can actually return.

WHY FOUR SEPARATE MOCKS, NOT ONE SHARED "GENERIC MEMORY STORE" MOCK
--------------------------------------------------------------------------------
Per the mission's central discipline ("never force Mem0/Letta/Graphiti/A-MEM into one
fake universal memory model"), each mock preserves the foundation-NATIVE shape the Step 2
audit (`capability_audit.py`) actually found:

- `MockMem0Adapter`: flat, scored, user/session-scoped memory records (no graph, no
  linking -- per the audit's `linking`/`graph` = NOT_SUPPORTED rows for OSS Mem0).
- `MockLettaAdapter`: a small core-memory-block + archival-memory-list split (the one
  piece of Letta's architecture this stage's audit could ground with reasonable
  confidence even from a thin README fetch), never claiming the richer detail the audit
  marked UNKNOWN.
- `MockGraphitiAdapter`: entity nodes + edges with temporal (valid_at/invalid_at)
  metadata, exposed as an actual nested graph structure via `inspect_memory()`/
  `export_state()` -- NEVER flattened to a bare list, per the audit's `graph`/
  `temporal_state` = SUPPORTED rows.
- `MockAMemAdapter`: memory notes carrying structured attributes (context/keywords/tags)
  plus a `linked_memory_ids` field that `update_memory()` calls on OTHER notes can mutate
  (memory evolution) -- per the audit's `update`/`linking` = SUPPORTED rows, which
  specifically found A-MEM's update semantics ("new memories can trigger updates to
  EXISTING memories' attributes") genuinely distinctive relative to Mem0/Graphiti.

Pure, deterministic, in-memory Python only: no filesystem/network/LLM/embeddings access
anywhere in this subpackage, no randomness (ids are caller-supplied or a deterministic
counter, never `uuid4()`/`random`).
"""

from __future__ import annotations

MOCK_CONFORMANCE = "MOCK_CONFORMANCE"

__all__ = ["MOCK_CONFORMANCE"]
