"""Phase 17 Workstream H -- canonical benchmark result matrix.

Assembles the headline, already-measured cells from Phases 4-17 into ONE table, keyed
by (attack, dataset, defense_config, generalization_setting). Every cell is either a
real number traced to its `source` artifact file, or the literal string "not measured"
(never a fabricated zero). This is NOT exhaustive (the full field list Workstream H names
would require re-deriving numbers this project never computed in a comparable shape for
every cell) -- it is scoped to the highest-value, already-real cells: the 7 attack
families x {signal_source, held_out_regen, held_out_evasion} x {B9-live, B11, B12}, plus
the held-out-novel-mechanism and Chinese rows, plus utility/latency. Gaps are disclosed
in `MATRIX_LIMITS` below, not silently filled.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

D = Path(__file__).parent / "data"
NA = "N/A"
NOT_MEASURED = "not measured"

MATRIX_LIMITS = (
    "Propagation/Sleeper/attribution metrics are reported in dedicated Phase 7-13 reports, "
    "not re-derived here in this matrix's row shape (would require re-running those studies "
    "under this matrix's exact schema; not attempted this round -- see 'not measured').",
    "PAR/PR/SDR/AMR/DGS (Phase 6/10/12 vocabulary) apply to configs and corpora this matrix's "
    "own held-out splits do not share 1:1 with the frozen Phase 6-12 corpus; cross-referencing "
    "them would require a fresh recomputation on Phase 17's own splits, not attempted.",
    "Memory-foundation column is 'clean agent (MockMem0Adapter)' for every row except the "
    "'live A-MEM' and 'live Mem0' rows (Track B poison only, 9 cases x 3 variants x "
    "{B0,B9,B11,B12}, sourced from `amem_live/stage2_results.json` and "
    "`mem0_live/stage2_results.json`); both required a separate isolated Python "
    "environment not committed to this repository (`C:\h4venv`, `C:\mem0venv`).",
)


def _get(d: dict, *path, default=NOT_MEASURED):
    cur = d
    for p in path:
        if cur is None or p not in cur:
            return default
        cur = cur[p]
    return cur


def build() -> List[dict]:
    b12 = json.loads((D / "b12_results.json").read_text(encoding="utf-8"))
    ext = json.loads((D / "extended_results.json").read_text(encoding="utf-8"))
    b11g = json.loads((D / "gstack2_results.json").read_text(encoding="utf-8"))
    amem = json.loads((D / "amem_live" / "stage2_results.json").read_text(encoding="utf-8")) if (D / "amem_live" / "stage2_results.json").exists() else \
           json.loads((Path(__file__).parent / "amem_live" / "stage2_results.json").read_text(encoding="utf-8"))
    rows: List[dict] = []

    def row(**kw):
        base = {"attack": NA, "dataset": "LoCoMo", "memory_foundation": "clean agent", "model": "qwen2.5:7b (judge) / llama2 (agent)",
                "defense": NA, "split": NA, "generalization_setting": NA, "detection_flagged": NOT_MEASURED,
                "detection_excluded": NOT_MEASURED, "fpr": NA, "evidence_status": "OBSERVED", "source": NA}
        base.update(kw)
        rows.append(base)

    for name, key, setting in (("signal_source", "signal_source", "in-sample (signals tuned on these)"),
                               ("held_out_regen", "held_out_regen", "held-out regenerated seed"),
                               ("held_out_evasion", "held_out_evasion", "held-out defense-aware paraphrase")):
        n = b12["poison"][key]["n"]
        row(attack="7 known families (mixed)", defense="B9-live", split=name, generalization_setting=setting,
            detection_flagged=f"{b12['poison'][key]['g1_f']['k']}/{n}", detection_excluded=f"{b12['poison'][key]['g1_x']['k']}/{n}",
            source="b12_results.json")
        row(attack="7 known families (mixed)", defense="B12", split=name, generalization_setting=setting,
            detection_flagged=f"{b12['poison'][key]['B12_flag']['k']}/{n}", detection_excluded=f"{b12['poison'][key]['B12_excl']['k']}/{n}",
            source="b12_results.json")

    n_nov = ext["novel_mechanisms"]["total"]["B9-live"]["flagged"]["n"]
    row(attack="6 unseen mechanisms (not any of the 7 families)", defense="B9-live", split="held_out_novel",
        generalization_setting="unseen attack MECHANISM (leave-mechanism-out)",
        detection_flagged=f"{ext['novel_mechanisms']['total']['B9-live']['flagged']['k']}/{n_nov}",
        detection_excluded=f"{ext['novel_mechanisms']['total']['B9-live']['excluded']['k']}/{n_nov}", source="extended_results.json")
    n_nov2 = b12["poison"]["held_out_novel"]["n"]
    row(attack="6 unseen mechanisms", defense="B12", split="held_out_novel", generalization_setting="unseen attack MECHANISM (leave-mechanism-out)",
        detection_flagged=f"{b12['poison']['held_out_novel']['B12_flag']['k']}/{n_nov2}",
        detection_excluded=f"{b12['poison']['held_out_novel']['B12_excl']['k']}/{n_nov2}", source="b12_results.json")

    n_zh = b12["poison"]["held_out_zh"]["n"]
    row(attack="7 known families (translated)", dataset="LoCoMo (Chinese translation)", defense="B12", split="held_out_zh",
        generalization_setting="unseen LANGUAGE", detection_flagged=f"{b12['poison']['held_out_zh']['B12_flag']['k']}/{n_zh}",
        detection_excluded=f"{b12['poison']['held_out_zh']['B12_excl']['k']}/{n_zh}", source="b12_results.json")

    for ds, key in (("LoCoMo-style pools", "dataset_arena"), ("ConvoMem", "convomem"), ("PerLTQA (Chinese)", "perltqa_zh")):
        n = b12["benign"][key]["n"]
        row(attack=NA, dataset=ds, defense="B12", split="benign", generalization_setting="unseen DATASET (benign FPR)",
            detection_flagged=NA, detection_excluded=NA, fpr=f"{b12['benign'][key]['B12_excl']['k']}/{n} excluded, {b12['benign'][key]['B12_flag']['k']}/{n} flagged",
            source="b12_results.json")

    for cfg in ("B0", "B9", "B11", "B12"):
        for kind in ("poison_original", "poison_plain", "poison_embedded"):
            a = amem["by_kind"][cfg][kind]
            row(attack="7 known families (real Track B)", dataset="LoCoMo", memory_foundation="LIVE A-mem-sys (real embeddings/ChromaDB/search)",
                defense=cfg, split=kind, generalization_setting="unseen MEMORY FOUNDATION (clean agent -> A-MEM)",
                detection_excluded=f"{a['poison_excluded']}/{a['n']}", detection_flagged=NOT_MEASURED,
                source="amem_live/stage2_results.json")

    mem0_path = Path(__file__).parent / "mem0_live" / "stage2_results.json"
    if mem0_path.exists():
        mem0 = json.loads(mem0_path.read_text(encoding="utf-8"))
        for cfg in ("B0", "B9", "B11", "B12"):
            for kind in ("poison_original", "poison_plain", "poison_embedded"):
                a = mem0["by_kind"][cfg][kind]
                row(attack="7 known families (real Track B)", dataset="LoCoMo", memory_foundation="LIVE Mem0 (real Qdrant/HuggingFace embeddings/search, LLM-free add path)",
                    defense=cfg, split=kind, generalization_setting="unseen MEMORY FOUNDATION (clean agent -> Mem0)",
                    detection_excluded=f"{a['poison_excluded']}/{a['n']}", detection_flagged=NOT_MEASURED,
                    source="mem0_live/stage2_results.json")

    return rows


def write_csv(rows: List[dict], path: Path) -> None:
    fields = ["attack", "dataset", "memory_foundation", "model", "defense", "split", "generalization_setting",
              "detection_flagged", "detection_excluded", "fpr", "evidence_status", "source"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    rows = build()
    (D / "canonical_matrix.json").write_text(json.dumps({"rows": rows, "limits": MATRIX_LIMITS}, indent=2), encoding="utf-8")
    write_csv(rows, D / "canonical_matrix.csv")
    print(len(rows), "rows written")
