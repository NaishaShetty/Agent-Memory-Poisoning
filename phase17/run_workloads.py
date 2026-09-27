import json
from pathlib import Path
from phase17 import workloads as W

CONFIGS = ("B1", "B2", "B4", "B8", "B9", "B10")
lo = W.locomo_cases_with_category()
lme = W.lme_cases_with_type()
agg_lo, ex_lo = W.stratify(lo, CONFIGS)
agg_lme, ex_lme = W.stratify(lme, CONFIGS)
out = {"locomo": W.to_report(agg_lo), "longmemeval": W.to_report(agg_lme),
       "n_locomo": len(lo), "n_lme": len(lme),
       "excluded_cases": [{"dataset": "locomo", "task_id": c.task_id, "config": cfg, "category": cat} for c, cfg, cat in ex_lo]
                         + [{"dataset": "longmemeval", "task_id": c.task_id, "config": cfg, "category": cat} for c, cfg, cat in ex_lme]}
Path("phase17/data/workload_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print("DONE", len(lo), len(lme), len(out["excluded_cases"]))
