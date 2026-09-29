"""Phase 17 Workstream J -- a minimal, real, canonical benchmark entry point.

    python -m phase17.bench_runner --defense B12 --split held_out_novel

Loads a named held-out poison split (or a benign population), applies a named REAL
defense config (`phase14.defended_retrieval.apply_defense`, the same frozen dispatcher
every Phase 14/17 live number already goes through -- this module adds NO new defense
logic), and emits ONE canonical, reproducible result artifact (JSON) with the schema
`docs/phase17/BENCHMARK_SPECIFICATION.md` defines. Does not replace any historical
experiment's own runner; it is the forward-facing interface for a NEW ad hoc run."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence, Tuple

SPLITS = {
    "signal_source": lambda: __import__("phase17.poison_sets", fromlist=["original_records"]).original_records(),
    "held_out_regen": lambda: __import__("phase17.poison_sets", fromlist=["regenerated_records"]).regenerated_records(),
    "held_out_evasion": lambda: __import__("phase17.poison_sets", fromlist=["evasion_records"]).evasion_records(),
    "held_out_novel": lambda: __import__("phase17.novel_attacks", fromlist=["novel_records"]).novel_records(),
    "held_out_zh": lambda: __import__("phase17.translation", fromlist=["zh_records"]).zh_records(),
    "held_out_extended": lambda: __import__("phase17.corpus_extended", fromlist=["extended_records"]).extended_records(),
}


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown (git unavailable)"


@dataclass(frozen=True)
class RunManifest:
    scenario_id: str
    split: str
    defense: str
    n_records: int
    git_commit: str
    python_version: str
    platform: str
    timestamp_utc: str
    seed_note: str


def run(split: str, defense: str, out_path: Path) -> dict:
    from phase14.defended_retrieval import REAL_CONFIGS, apply_defense
    from phase17.arenas import isolated_arena

    if defense not in REAL_CONFIGS:
        raise ValueError(f"Unknown defense {defense!r}; must be one of {REAL_CONFIGS!r}")
    if split not in SPLITS:
        raise ValueError(f"Unknown split {split!r}; must be one of {sorted(SPLITS)!r}")
    records = SPLITS[split]()
    # CORRECTION (external review round 3, follow-up, 2026-09-28): this used to put all
    # `records` into ONE shared pool with apply_defense(defense, items), with no benign
    # distractors at all. The published numbers this runner is supposed to reproduce use
    # `phase17.arenas.isolated_arena` -- one real candidate pool PER record, each with 3
    # real benign distractors -- because pool-relative signals (e.g. B9's
    # retrieval-consensus divergence, computed from the OTHER items in the same pool) give
    # a genuinely different answer depending on what else is in the pool. Confirmed by
    # direct comparison on held_out_novel: the one-big-pool version reproduced B12 exactly
    # (44/35, pool-independent) but not B9 (1/0 vs published 5/0) or B11's flag count
    # (47/20 vs published 44/20) -- both of which DO depend on pool composition. Fixed by
    # building the same one-pool-per-record structure with real distractors and calling
    # apply_defense once per pool, keeping only each record's own decision.
    by_family = {r.scenario_id: r.family for r in records}
    pools, _truth = isolated_arena(records)
    rows = []
    for pool in pools:
        pool_items: Tuple[Tuple[str, str], ...] = tuple((m.scenario_id, m.content_text) for m in pool.memories)
        _, decisions = apply_defense(defense, pool_items)
        poison_id = pool.memories[0].scenario_id  # isolated_arena always puts the poison record first
        d = next(dec for dec in decisions if dec.memory_id == poison_id)
        rows.append({"scenario_id": d.memory_id, "family": by_family.get(d.memory_id),
                    "action": d.action, "excluded": d.excluded, "flagged": d.action != "ALLOW"})
    n = len(rows)
    manifest = RunManifest(
        scenario_id=f"bench-{split}-{defense}", split=split, defense=defense, n_records=n, git_commit=_git_commit(),
        python_version=sys.version.split()[0], platform=platform.platform(),
        timestamp_utc=datetime.now(timezone.utc).isoformat(), seed_note="detectors/judges are seeded and cached; see cache files in phase17/data/",
    )
    result = {"manifest": asdict(manifest), "summary": {
        "flagged": sum(r["flagged"] for r in rows), "excluded": sum(r["excluded"] for r in rows), "n": n},
        "rows": rows}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


def main(argv: Sequence[str] = None) -> int:
    p = argparse.ArgumentParser(description="MAMBench Phase 17 canonical benchmark runner")
    p.add_argument("--defense", required=True, help="a REAL_CONFIGS name, e.g. B0, B9, B11, B12")
    p.add_argument("--split", required=True, choices=sorted(SPLITS))
    p.add_argument("--out", default=None, help="output JSON path (default: phase17/data/bench_runs/<split>_<defense>.json)")
    args = p.parse_args(argv)
    out = Path(args.out) if args.out else Path(__file__).parent / "data" / "bench_runs" / f"{args.split}_{args.defense}.json"
    result = run(args.split, args.defense, out)
    print(json.dumps(result["summary"], indent=2))
    print(f"result written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
