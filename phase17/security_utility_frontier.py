"""Phase 17 Workstream D -- security-utility frontier: ONE table across every already-
measured config (B0/B1/B9/B10/B11/B12), assembled from existing result artifacts (this
module runs no new experiments; every number is traced to its source file in `source`).
Never ranks a "winner" -- the frontier itself is the deliverable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

D = Path(__file__).parent / "data"


def _load(name: str) -> Optional[dict]:
    p = D / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def build() -> Dict[str, dict]:
    b12 = _load("b12_results.json")
    b11 = _load("gstack2_results.json")
    util11 = _load("utility_b11.json")
    util12 = _load("utility_b12.json")
    ext = _load("extended_results.json")

    rows: Dict[str, dict] = {}

    def util_row(u: dict, cfg: str) -> dict:
        return {"track_a_success_n": u["track_a_combined"][cfg]["n_success"], "track_a_n": 300,
                "urs": u["urs_combined"].get(cfg), "track_b_forged": u["track_b"][cfg]["n_matches_forged"],
                "track_b_excluded": u["track_b"][cfg]["n_poison_excluded"], "track_b_n": u["track_b"][cfg]["n_tasks"]}

    if util12:
        rows["B0"] = {"detection_novel": None, "fpr_dataset_arena": None, **util_row(util12, "B0"), "latency_note": "no defense (bound: ALWAYS_ALLOW)",
                      "source": "utility_b12.json"}
        rows["B9-live"] = {"detection_novel": ext["novel_mechanisms"]["total"]["B9-live"]["excluded"] if ext else None,
                           "fpr_dataset_arena": None, **util_row(util12, "B9"), "latency_note": "1 admission pass, no LLM",
                           "source": "utility_b12.json, extended_results.json"}
        rows["B10"] = {"detection_novel": None, "fpr_dataset_arena": None, **util_row(util12, "B10"),
                       "latency_note": "1 admission pass + untrained GNN/GLN blend, no LLM", "source": "utility_b12.json"}
        rows["B12"] = {"detection_novel": b12["poison"]["held_out_novel"]["B12_excl"] if b12 else None,
                       "fpr_dataset_arena": b12["benign"]["dataset_arena"]["B12_excl"] if b12 else None,
                       **util_row(util12, "B12"), "latency_note": "1 admission pass + ~0.4s/memory (2 judge calls) + embedding",
                       "source": "utility_b12.json, b12_results.json"}
    if util11:
        rows["B11"] = {"detection_novel": b11["poison"]["held_out_novel"]["B11_excl"] if b11 else None,
                       "fpr_dataset_arena": b11["benign"]["dataset_arena"]["B11_excl"] if b11 else None,
                       **util_row(util11, "B11"), "latency_note": "1 admission pass + ~0.2-0.4s/memory (1-2 judge calls)",
                       "source": "utility_b11.json, gstack2_results.json"}
    return rows


def to_markdown(rows: Dict[str, dict]) -> str:
    hdr = "| Config | Novel-mechanism excluded | Dataset-arena benign excluded | Track-A success (n=300) | URS | Track-B forged (n=9) | Latency |\n"
    hdr += "|---|---|---|---|---|---|---|\n"
    lines = [hdr]
    for cfg, r in rows.items():
        det = f"{r['detection_novel']['k']}/{r['detection_novel']['n']}" if r.get("detection_novel") else "not measured"
        fpr = f"{r['fpr_dataset_arena']['k']}/{r['fpr_dataset_arena']['n']}" if r.get("fpr_dataset_arena") else "not measured"
        urs = f"{r['urs']:.3f}" if r.get("urs") is not None else "N/A (baseline)"
        lines.append(f"| {cfg} | {det} | {fpr} | {r['track_a_success_n']}/{r['track_a_n']} | {urs} | {r['track_b_forged']}/{r['track_b_n']} | {r['latency_note']} |")
    return "".join(lines[:1]) + "\n".join(lines[1:])


if __name__ == "__main__":
    rows = build()
    (D / "security_utility_frontier.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    md = to_markdown(rows)
    (D / "security_utility_frontier.md").write_text(md, encoding="utf-8")
    print(md)
