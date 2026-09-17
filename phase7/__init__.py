"""Phase 7 -- Propagation Monitoring.

See docs/phase7/PHASE7_PLAN.md for the charter this package implements against.
Every module here is a read-only consumer of Phase 5's lineage/trace-assembly
output (`phase5.wiring.lineage`, `phase5.wiring.trace_assembly`) and Phase 3's
`taint_propagation.py` -- none of them is modified, and no new edge type or
evidence kind is introduced (Phase 7 plan, Acceptance Criteria for 7.1).
"""
