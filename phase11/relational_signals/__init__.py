"""Phase 11.y -- relational/semantic signal discovery.

ISOLATED, OFF-BY-DEFAULT INVESTIGATION. Nothing here is imported by, or
changes the behavior of, the existing Phase 11 GNN/GLN, `phase11/hybrid.py`,
`phase11/evaluation/run_b10.py`, Option 1, Option 2, or Track A/B. Those
findings remain frozen and are not reinterpreted by this package.

`held_out_pools()` is never imported or referenced anywhere in this
package -- verified directly (bytecode name references, not text search) by
`phase11/tests/test_relational_signals.py::test_no_held_out_access`.
"""
