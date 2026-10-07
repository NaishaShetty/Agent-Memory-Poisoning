"""Round 7 item 8: a BLIND human-annotation sheet for the LLM judges, and the agreement scorer.

Every compliance, harm and mechanism label in this benchmark comes from an LLM judge. Their error
rate has been argued about (judge families chosen for independence, an out-of-loop judge for
mechanism) but never measured against people. This makes measuring it a short, well-defined task:

  `python -m phase17.human_labels build`   writes docs/phase17/human_labels/sheet.csv -- 100 items,
                                           NO judge verdicts in it -- and a separate key file the
                                           annotator must not open
  (a person fills the `human_label` column with YES or NO, using the question in each row)
  `python -m phase17.human_labels score`   per judge: agreement, Cohen's kappa, and both error rates

Strata (seeded): 40 compliance judgements on hold-out 5 (llama3.1), 40 harm judgements from the
harm study (llama3.1), 20 mechanism judgements on hold-out 4 (Gemini). Within each, items are
balanced between judge-YES and judge-NO where possible, so the false-positive and false-negative
error rates of the judge can both be estimated rather than only its accuracy on the majority class.
The sheet is shuffled so judge types and verdicts are not grouped.
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).parent / "data"
DIR = ROOT / "docs" / "phase17" / "human_labels"
SHEET, KEY, OUT = DIR / "sheet.csv", DIR / "KEY_do_not_open_while_labelling.json", DATA / "human_label_agreement.json"
SEED = 2026


def _balanced(rows, n, rng):
    yes = [r for r in rows if r["judge"]]
    no = [r for r in rows if not r["judge"]]
    rng.shuffle(yes); rng.shuffle(no)
    k = min(n // 2, len(yes), len(no))
    pick = yes[:k] + no[:k]
    rest = [r for r in yes[k:] + no[k:]]
    rng.shuffle(rest)
    return pick + rest[: n - len(pick)]


def build() -> dict:
    from phase17.holdout4_corpus import attack_records as h4a
    from phase17.holdout5_corpus import attack_records as h5a
    from phase17.holdout4_validity import MECH_Q
    from phase17.neutralise_v2 import COMPLY_Q, _key

    rng = random.Random(SEED)
    comp = []
    done = {}
    for f in ("neutralise_v2_partial.json", "compose_neutralise_partial.json"):
        p = DATA / f
        if p.exists():
            done.update(json.loads(p.read_text(encoding="utf-8")))
    jd = {}
    for f in ("neutralise_v2_judge.json", "compose_neutralise_judge.json"):
        p = DATA / f
        if p.exists():
            jd.update(json.loads(p.read_text(encoding="utf-8")))
    for r in h5a():
        a = done.get(_key("a", "raw", r.text))
        if not a:
            continue
        v = jd.get(_key("j", COMPLY_Q[:12], r.text + "||" + a))
        if v is None:
            continue
        comp.append({"type": "compliance", "note": r.text, "answer": a, "question": COMPLY_Q, "judge": bool(v)})

    from phase17 import harm_study_v2 as H
    own = json.loads((DATA / "neutralise_own_partial.json").read_text(encoding="utf-8"))
    pub = {r["id"]: r for r in json.loads((DATA / "harm_study_v2.json").read_text(encoding="utf-8"))["rows"]}
    harm = []
    for k, v in own.items():
        if not k.startswith("raw:"):
            continue
        pid = k[4:]
        p = pub.get(pid)
        if p:
            harm.append({"type": "harm", "note": p["poison_text"], "answer": v["ans"],
                         "question": p["judge_question"], "judge": bool(v["harm"])})

    mech = json.loads((DATA / "holdout4_mechanism.json").read_text(encoding="utf-8"))["per_item"]
    mrows = [{"type": "mechanism", "note": r.text, "answer": "", "question": MECH_Q[r.family],
              "judge": bool(mech[r.scenario_id])} for r in h4a() if r.scenario_id in mech]

    items = _balanced(comp, 40, rng) + _balanced(harm, 40, rng) + _balanced(mrows, 20, rng)
    rng.shuffle(items)
    DIR.mkdir(parents=True, exist_ok=True)
    with open(SHEET, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "question", "memory_note", "assistant_answer", "human_label (YES/NO)", "comment"])
        for i, it in enumerate(items):
            w.writerow([i, it["question"], it["note"], it["answer"] or "(no answer -- judge the NOTE itself)", "", ""])
    KEY.write_text(json.dumps([{"item": i, "type": it["type"], "judge": it["judge"]}
                               for i, it in enumerate(items)], indent=1), encoding="utf-8")
    return {"n": len(items), "by_type": {t: sum(it["type"] == t for it in items)
                                         for t in ("compliance", "harm", "mechanism")}}


def score() -> dict:
    key = {k["item"]: k for k in json.loads(KEY.read_text(encoding="utf-8"))}
    with open(SHEET, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    lab = {int(r["item"]): r["human_label (YES/NO)"].strip().upper() for r in rows}
    out = {"by_type": {}}
    for t in ("compliance", "harm", "mechanism", "ALL"):
        pairs = [(key[i]["judge"], lab[i] == "YES") for i in lab
                 if lab[i] in ("YES", "NO") and (t == "ALL" or key[i]["type"] == t)]
        n = len(pairs)
        if not n:
            out["by_type"][t] = {"n_labelled": 0}
            continue
        agree = sum(j == h for j, h in pairs) / n
        pj = sum(j for j, _ in pairs) / n
        ph = sum(h for _, h in pairs) / n
        pe = pj * ph + (1 - pj) * (1 - ph)
        kappa = (agree - pe) / (1 - pe) if pe < 1 else None
        fp = sum(j and not h for j, h in pairs)
        fn = sum(h and not j for j, h in pairs)
        out["by_type"][t] = {"n_labelled": n, "agreement": round(agree, 3),
                             "cohen_kappa": None if kappa is None else round(kappa, 3),
                             "judge_yes_human_no": fp, "judge_no_human_yes": fn}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys

    print(json.dumps(score() if "score" in sys.argv else build(), indent=1))
    print("DONE")
