import json
from pathlib import Path
from phase17.perltqa import perltqa_pools
from phase17.stacked_detector import StackedDetector
from phase17.stats import rate_with_ci
from phase17.translation import zh_records

def main():
    det = StackedDetector.load(Path(__file__).parent / "data" / "stacked_model.json")
    tx = [r.text for r in zh_records()]
    out = {"zh_poison": {}, "perltqa_benign_odd_pools": {}}
    for route in ("judge_only", "translate"):
        out["zh_poison"][route] = {"excluded": rate_with_ci(sum(det.decide(tx, 0.005, route)), len(tx)),
                                   "flagged": rate_with_ci(sum(det.decide(tx, 0.02, route)), len(tx))}
    te = sorted(perltqa_pools()[0], key=lambda p: p.pool_id)[1::2]
    bt = [m.content_text for p in te for m in p.memories]
    out["perltqa_benign_odd_pools"]["translate"] = {"excluded": rate_with_ci(sum(det.decide(bt, 0.005, "translate")), len(bt)),
                                                    "flagged": rate_with_ci(sum(det.decide(bt, 0.02, "translate")), len(bt))}
    Path(__file__).parent.joinpath("data", "zh_route_results.json").write_text(json.dumps(out, indent=2))
    f = lambda x: f"{x['k']}/{x['n']}"
    print("DONE", {k: {r: (f(v['excluded']), f(v['flagged'])) for r, v in d.items()} for k, d in out.items()})

if __name__ == "__main__":
    main()
