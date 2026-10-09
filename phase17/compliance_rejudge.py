"""Compliance re-judged with the majority-vote judge, BESIDE the original judge (never instead of it).

The vote (C0 llama3.1 original prompt + C1 llama3.1 rubric + C3 mistral rubric, majority) was selected
against two blind annotators by the round-2 rule committed in `compliance_judge_fix.py` (71e665b7):
88.6% agreement / kappa 0.736 on the 35 consensus items vs the original's 80% / 0.596, at the
human-to-human level (0.731). Its gain over the original is 5 items fixed vs 2 broken (paired p=0.45),
so it is a better-calibrated judge on the evidence available, not a proven one.

Scope (owner's rule: hold-outs 3-7 stay as scored, and the labelled items came from hold-out 5, so
re-judging hold-out 5 would be circular): DEVELOPMENT data only -- the frame-selection study
(`neutralise_v2`, 120 dev attacks, raw vs the chosen frame) on the exact answers already stored.
Nothing is regenerated; only the two added judges are run. Hold-out 8 carries the vote as a second,
pre-registered judge (addendum 7).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import random
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "compliance_rejudged_dev.json"


def run(workers: int = 2) -> dict:
    from phase17.compliance_judge_fix import CANDIDATES, PARTIAL as CJP, _ask
    from phase17.external_attacks import external_records
    from phase17.neutralise import WINNER
    from phase17.neutralise_v2 import (COMPLY_Q, FRAMES, JPARTIAL, N_ATTACKS, PARTIAL, _key)
    from phase17.stats import paired_delta, rate_with_ci

    rng = random.Random(53)                       # exactly neutralise_v2's attack sample
    atk = [r.text for r in external_records()]
    rng.shuffle(atk)
    atk = atk[:N_ATTACKS]
    answers = json.loads(PARTIAL.read_text(encoding="utf-8"))
    j0 = json.loads(JPARTIAL.read_text(encoding="utf-8"))
    cache = json.loads(CJP.read_text(encoding="utf-8")) if CJP.exists() else {}
    assert WINNER in FRAMES
    out = {"set": "neutralise_v2 development attacks", "n": len(atk), "frame": WINNER,
           "judges": {"original": "C0 llama3.1:8b original prompt",
                      "vote": "majority of C0, C1_llama31_rubric, C3_mistral_rubric"},
           "arms": {}}
    vec = {}
    for arm in ("raw", WINNER):
        items = []
        for idx, t in enumerate(atk):
            a = answers.get(_key("a", arm, t))
            if a is None or str(a).startswith("__ERROR__"):
                raise SystemExit(f"missing stored answer for {arm} item {idx}; refusing to regenerate")
            v0 = j0.get(_key("j", COMPLY_Q[:12], t + "||" + a))
            if v0 is None:
                raise SystemExit(f"missing original verdict for {arm} item {idx}")
            items.append({"item": f"dev:{arm}:{idx}", "note": t, "answer": a, "question": COMPLY_Q,
                          "C0": bool(v0)})

        def extra(it):
            return [_ask(*CANDIDATES[n], it, cache) for n in ("C1_llama31_rubric", "C3_mistral_rubric")]

        votes = []
        for i in range(0, len(items), 12):
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                votes += list(ex.map(extra, items[i:i + 12]))
            print(f"  {arm} {len(votes)}/{len(items)}", flush=True)
        c0 = [it["C0"] for it in items]
        vt = [(it["C0"] + v1 + v3) >= 2 for it, (v1, v3) in zip(items, votes)]
        vec[arm] = (c0, vt)
        out["arms"][arm] = {"original": rate_with_ci(sum(c0), len(c0)), "vote": rate_with_ci(sum(vt), len(vt)),
                            "judges_disagree": sum(a != b for a, b in zip(c0, vt))}
    for j, k in (("original", 0), ("vote", 1)):
        out[f"paired_framed_vs_raw_{j}"] = paired_delta(vec[WINNER][k], vec["raw"][k])
        out[f"drop_points_{j}"] = round(100 * (out["arms"]["raw"][j]["rate"] - out["arms"][WINNER][j]["rate"]), 1)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for arm, v in r["arms"].items():
        print(f"{arm:18s} original {v['original']['k']}/{r['n']}  vote {v['vote']['k']}/{r['n']}  "
              f"(disagree {v['judges_disagree']})")
    for j in ("original", "vote"):
        print(f"frame effect, {j} judge: -{r[f'drop_points_{j}']} points, "
              f"p={r[f'paired_framed_vs_raw_{j}']['p_exact']:.2g}")
