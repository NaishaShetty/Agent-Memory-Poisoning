"""Stage 0 (main interpreter): dump the live-A-MEM test cases to JSON so the isolated
`C:\h4venv` interpreter (which has A-mem-sys, chromadb, litellm) needs no repo imports.
Cases: 9 real Track B poison cases, their 18 plain/embedded evasion variants, and 30 real
LoCoMo benign Track A cases."""
import json
from pathlib import Path

from phase14.track_b_poison import build_track_b_cases
from phase17.poison_sets import evasion_records
from phase17.workloads import locomo_cases_with_category

OUT = Path(__file__).parent / "inputs.json"


def main():
    evr = {(r.parent_id, r.variant): r.text for r in evasion_records()}
    cases = []
    for c in build_track_b_cases():
        base = list(c.pool_items)
        cases.append({"kind": "poison_original", "id": c.task_id, "question": c.question, "poison_id": base[0][0], "items": base})
        for v in ("plain", "embedded"):
            if (c.target_scenario_id, v) in evr:
                items = [(base[0][0], evr[(c.target_scenario_id, v)])] + base[1:]
                cases.append({"kind": f"poison_{v}", "id": f"{c.task_id}-{v}", "question": c.question, "poison_id": base[0][0], "items": items})
    for case, _cat in locomo_cases_with_category()[:30]:
        cases.append({"kind": "benign", "id": case.task_id, "question": case.question, "poison_id": None, "items": list(case.pool_items)})
    OUT.write_text(json.dumps(cases, indent=1), encoding="utf-8")
    print(len(cases))


if __name__ == "__main__":
    main()
