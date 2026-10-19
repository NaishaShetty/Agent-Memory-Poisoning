"""v7 cache isolation. Every v6 module whose cache path is a module constant is re-pointed to a v7 file BEFORE any call.
Import this module first in every v7 entry point. Shared judge caches (phase17/data/judge_cache.json,
judge_score_cache.json) are written by additions only, as in v2-v6, and verified by `verify_shared_caches()`.
"""
from __future__ import annotations

from phase17.defence_v7 import atomic  # noqa: F401  (crash-safe checkpoints: atomic file writes)

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "phase17" / "data" / "defence_v7"
DEC_CACHE = DATA / "v7_decisions_cache.json"
NLI_CACHE = DATA / "v7_nli_cache.json"          # Gap 2 (g2_dev, dcr, g2_v7)
NLI_G1 = DATA / "v7_nli_g1.json"                 # Gap 1 reference mapping (separate file: no cross-process writes)
SIG_CACHE = DATA / "v7_signals.json"
BEH_PARTIAL = DATA / "v7_behaviour_partial.json"
SHARED = ("phase17/data/judge_cache.json", "phase17/data/judge_score_cache.json")


def isolate() -> None:
    from phase17.defence_v3 import vpl
    from phase17.defence_v4 import voa
    from phase17.defence_v6 import fpb, g1_eval, g3_eval

    vpl.CACHE = DEC_CACHE
    g1_eval.DEC_CACHE = DEC_CACHE
    fpb.NLI_CACHE = NLI_G1
    g3_eval.SIG = SIG_CACHE
    voa.PARTIAL = BEH_PARTIAL
    g3_eval.V.PARTIAL = BEH_PARTIAL
    g1_eval.SEL = ROOT / "phase17" / "data" / "defence_v6" / "clp_selection.json"    # read only (frozen delta)
    g1_eval.OUT = DATA / "_unused_v6_g1_out.json"                                      # v6 writers never target v6 files
    g3_eval.SELK = ROOT / "phase17" / "data" / "defence_v6" / "g3_selection.json"     # read only (frozen K)
    g3_eval.OUT = DATA / "_unused_v6_g3_out.json"


def verify_shared_caches(ref: str = "HEAD") -> dict:
    """No key removed or changed in the shared judge caches relative to `ref`."""
    out = {}
    for f in SHARED:
        new = json.loads((ROOT / f).read_text(encoding="utf-8"))
        old = json.loads(subprocess.check_output(["git", "show", f"{ref}:{f}"], cwd=ROOT).decode("utf-8"))
        out[f] = {"old": len(old), "new": len(new), "removed": sum(k not in new for k in old),
                  "changed": sum(k in new and new[k] != old[k] for k in old), "added": sum(k not in old for k in new)}
    return out
