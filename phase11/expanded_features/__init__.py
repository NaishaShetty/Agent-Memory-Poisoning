"""Phase 11.x Option 2 -- expanded feature vocabulary investigation.

ISOLATED, OFF-BY-DEFAULT EXPERIMENTAL PATH. Nothing in this package is
imported by, or changes the behavior of, any existing Phase 6-10 module, the
existing `phase11/gnn/`, `phase11/gln/`, `phase11/hybrid.py`,
`phase11/evaluation/run_b10.py`, or the Phase 11.x Option-1 investigation
(`phase11/gnn/relation_model.py`, `phase11/gnn/self_supervised.py`,
`phase11/tests/test_relation_aware_anomaly_investigation.py`). Those remain
exactly as they were, and their real, documented result --

    "The current 9-dimensional sanctioned Phase 6/10 feature vocabulary does
    not provide a reliable compact-benign-region vs poison-anomaly structure
    at the present data scale."

-- is a standing finding, not something this package overwrites, weakens, or
retroactively reinterprets. This package answers a narrower, separate
question: does adding genuinely new (not merely re-derived), non-circular
structural and/or semantic information change that answer? A "no" here is
just as valid and reportable a result as a "yes" (Section 3/13 of the
governing instructions).

`EXPANDED_FEATURES_ENABLED` is `False` -- no production code path reads it
or is gated by it (there is none to gate; this package is not wired into
`run_b10.py` or any shipped pipeline), but it is exported per Section 2's
explicit "switchable/off by default" requirement so a future integration
attempt has an explicit, discoverable flag to check rather than assuming
opt-in silently.
"""

EXPANDED_FEATURES_ENABLED = False
