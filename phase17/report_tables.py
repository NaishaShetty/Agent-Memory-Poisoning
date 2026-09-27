"""Phase 17 -- render ablation_results.json as compact markdown tables (used
by the report; never hand-typed numbers)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

RESULTS = Path(__file__).parent / "data" / "ablation_results.json"
DETECT_COLS = ["isolated:in_sample(original15)", "isolated:held_out_regen", "isolated:held_out_evasion",
               "coordinated:in_sample(original15)", "coordinated:held_out_regen", "frozen75:frozen75"]


def _cell(c: dict, with_p: bool = True) -> str:
    s = f"{c['k']}/{c['n']}"
    if with_p and "vs_full" in c:
        v = c["vs_full"]
        if v["only_a"] or v["only_b"]:
            s += f" (lost {v['only_a']}/gained {v['only_b']}, p={v['p_exact']:.2f}, holm={v.get('p_holm', 1.0):.2f})"
    return s


def table(system: str, key: str = "flagged", results=None, only_changed: bool = False) -> str:
    results = results or json.loads(RESULTS.read_text(encoding="utf-8"))
    rows: List[str] = []
    hdr = "| variant | " + " | ".join(DETECT_COLS) + " | FPR benign_locomo | FPR datasets(502) | FPR frozen75 |"
    rows += [hdr, "|" + "---|" * (len(DETECT_COLS) + 4)]
    for name, r in results[system].items():
        det = [r["detect"].get(f"{c}|{key}") for c in DETECT_COLS]
        if only_changed and name != "FULL" and name != "FULL(B8)" and all(
            (d is None) or ("vs_full" not in d) or (d["vs_full"]["only_a"] == 0 and d["vs_full"]["only_b"] == 0)
            for d in det
        ):
            continue
        fpr_loc = r["fpr"].get(f"benign_locomo|{key}")
        ds_k = sum(v["k"] for k, v in r["fpr"].items() if k.endswith(f"|{key}") and k.split("|")[0] in
                   ("benign_locomo", "benign_longmemeval", "benign_msc", "benign_conversation_chronicles"))
        ds_n = sum(v["n"] for k, v in r["fpr"].items() if k.endswith(f"|{key}") and k.split("|")[0] in
                   ("benign_locomo", "benign_longmemeval", "benign_msc", "benign_conversation_chronicles"))
        fz = r["fpr"].get(f"frozen75|{key}")
        rows.append(
            f"| {name} | " + " | ".join(_cell(d) if d else "-" for d in det)
            + f" | {_cell(fpr_loc, False) if fpr_loc else '-'} | {ds_k}/{ds_n} | {_cell(fz, False) if fz else '-'} |"
        )
    return "\n".join(rows)


if __name__ == "__main__":
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    for system in res:
        for key in ("flagged", "excluded"):
            print(f"\n### {system} -- detection/FPR as {key.upper()}\n")
            print(table(system, key, res, only_changed=True))
