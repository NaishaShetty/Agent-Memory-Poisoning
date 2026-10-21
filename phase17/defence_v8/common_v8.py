"""v8 cache isolation, mirroring phase17.defence_v7.common's pattern. Every shared module whose
cache path is a module-level constant is re-pointed to a v8-only file BEFORE any call, so
scoring SA-8 can never write into phase17/data/defence_v7/* (frozen, guarded by
test_v7_frozen.py) or phase17/data/defence_v6/*. v8 reads v7 CODE (g3_v7.limits, the K
constant, v6's G3._conditions) but never v7 or v6 DATA.

Import this module and call isolate() first in every v8 scoring entry point.
"""
from __future__ import annotations

from phase17.defence_v7 import atomic  # noqa: F401  (crash-safe checkpoints: atomic file writes)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "phase17" / "data" / "defence_v8"
DEC_CACHE = DATA / "v8_decisions_cache.json"
SIG_CACHE = DATA / "v8_signals.json"
BEH_PARTIAL = DATA / "v8_behaviour_partial.json"


def isolate() -> None:
    from phase17.defence_v3 import vpl
    from phase17.defence_v4 import voa
    from phase17.defence_v6 import g3_eval

    vpl.CACHE = DEC_CACHE
    g3_eval.SIG = SIG_CACHE
    voa.PARTIAL = BEH_PARTIAL
    g3_eval.V.PARTIAL = BEH_PARTIAL
