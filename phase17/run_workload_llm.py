import json
from pathlib import Path
from phase17 import workloads as W
from phase14.track_a_benign import run_track_a_case
from phase14.track_a_longmemeval import run_track_a_longmemeval_case

d = json.loads(Path("phase17/data/workload_results.json").read_text())
lo = {c.task_id: (c, cat) for c, cat in W.locomo_cases_with_category()}
lme = {c.task_id: (c, cat) for c, cat in W.lme_cases_with_type()}
rows = []
for e in d["excluded_cases"]:
    src = lo if e["dataset"] == "locomo" else lme
    fn = run_track_a_case if e["dataset"] == "locomo" else run_track_a_longmemeval_case
    case, cat = src[e["task_id"]]
    b0 = fn(case, "B0")
    dfd = fn(case, e["config"])
    rows.append({**e, "b0_success": bool(b0["success"]), "defended_success": bool(dfd["success"]), "target_excluded": bool(dfd["target_excluded"])})
    print(rows[-1])
Path("phase17/data/workload_llm_results.json").write_text(json.dumps(rows, indent=2))
print("DONE", len(rows))
