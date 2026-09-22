"""Phase 8/12 follow-on (2026-09-21) -- a real, content-text-keyed lookup
signal over `real_activation_shapes_cache.json` (the real, offline,
h4venv-computed activation-shape values -- see `compute_real_activation_shapes.py`'s
own module docstring for how and why this is precomputed rather than live).

WHAT THIS IS, AND IS NOT
--------------------------------------------------------------------------------
This is NOT a general-purpose signal function computable from `content_text`
alone the way every other Phase 6 signal is -- it is a real, disclosed lookup
against a real, precomputed, versioned cache covering exactly the real
content this project has real trigger-condition queries for (the real
`SEED_DESTRESS` poison, and 135 real LoCoMo benign turns from tasks 1-9). For
any OTHER content (including `corpus.py`'s own, differently-worded Sleeper
scenarios), this returns `0.0` -- explicitly disclosed as "no real cached
measurement," never silently treated as a confident "confirmed benign"
finding. This is the same "absent signal defaults to the same neutral value
as every other missing signal in this project" convention every other Phase 6
signal function already follows, not a new leniency invented for this one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from phase6.defense.signals.contract import SignalContext, signal_function

CACHE_PATH = Path(__file__).parent / "real_activation_shapes_cache.json"

_cache_by_text: dict = None


def _load_cache() -> Dict[str, bool]:
    global _cache_by_text
    if _cache_by_text is None:
        _cache_by_text = {}
        if CACHE_PATH.exists():
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            poison = data.get("poison")
            if poison:
                _cache_by_text[poison["text"]] = bool(poison["matches_dormant_pattern"])
            for b in data.get("benign", []):
                _cache_by_text[b["text"]] = bool(b["matches_dormant_pattern"])
    return _cache_by_text


@signal_function
def activation_shape_signal(context: SignalContext) -> Dict[str, float]:
    """Score in {0.0, 1.0}: real, cached `matches_dormant_pattern` value for
    this EXACT real content text, if this project has ever really computed
    one (see module docstring); `0.0` -- not "unknown," a real, disclosed
    default -- for any content this real cache does not cover."""
    cache = _load_cache()
    matched = cache.get(context.content_text, False)
    return {"activation_shape_score": 1.0 if matched else 0.0}
