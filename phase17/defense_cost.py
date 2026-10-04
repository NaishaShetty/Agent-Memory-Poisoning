"""Latency and cost per defended memory (external review round 5, PART 2.3).

"A defense that wins by blocking everything does not count" — and one that wins by spending
ten model calls per memory has a cost that belongs next to its recall number. B14 fuses five
model-backed detectors where B12 used one embedding plus one judge, so it is unambiguously
more expensive; this measures by how much rather than leaving it implied.

Measured on a COLD cache (every cache entry for the sample is removed first, then restored),
because a warm cache measures the cache, not the defense. Reported per memory, sequential
(the honest per-item cost) — the 8-way batching used elsewhere in this project is a
throughput optimization for bulk evaluation, not something a live single-memory admission
path can rely on.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Sequence

OUT = Path(__file__).parent / "data" / "defense_cost.json"
CONFIGS = ("B9", "B12", "B13", "B14", "B15")
N = 12


def _sample(n: int = N) -> List[str]:
    from phase17.novel_attacks import novel_records

    return [r.text for r in novel_records()[:n]]


def _cache_files() -> List[Path]:
    d = Path(__file__).parent / "data"
    return [d / "judge_cache.json", d / "judge_score_cache.json", d / "external_baseline_scores.json"]


def _purge(texts: Sequence[str]):
    """Remove just this sample's entries from every cache, returning what was removed so the
    caches can be restored afterwards -- a cost measurement must not destroy real cached work."""
    import hashlib

    removed = {}
    frags = [hashlib.sha256(t.encode("utf-8")).hexdigest()[:24] for t in texts]
    for p in _cache_files():
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        gone = {k: v for k in list(d) for v in [d[k]] if any(f in k for f in frags)}
        for k in gone:
            d.pop(k, None)
        if gone:
            p.write_text(json.dumps(d), encoding="utf-8")
        removed[str(p)] = gone
    return removed


def _restore(removed):
    for path, entries in removed.items():
        p = Path(path)
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        d.update(entries)
        p.write_text(json.dumps(d), encoding="utf-8")


def run(n: int = N) -> dict:
    from phase14.defended_retrieval import apply_defense

    texts = _sample(n)
    out = {"n_memories": len(texts), "note": "cold cache, sequential, one memory per pool", "per_config": {}}
    for cfg in CONFIGS:
        removed = _purge(texts)
        try:
            t0 = time.time()
            for i, t in enumerate(texts):
                apply_defense(cfg, ((f"COST-{i}", t),))
            dt = time.time() - t0
        finally:
            _restore(removed)
        out["per_config"][cfg] = {"total_seconds": round(dt, 2), "seconds_per_memory": round(dt / len(texts), 2)}
        print(f"  {cfg}: {dt/len(texts):.2f}s per memory (cold)", flush=True)
    base = out["per_config"]["B12"]["seconds_per_memory"]
    for cfg, v in out["per_config"].items():
        v["relative_to_B12"] = round(v["seconds_per_memory"] / base, 2) if base else None
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps(r["per_config"], indent=1))
    print("DONE")
