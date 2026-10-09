"""The ONE scoring of hold-out 8 (owner decision, 2026-10-09: improvements are tested on a new hold-out,
never by re-tuning on hold-outs 3-7).

REFUSES TO RUN unless `docs/phase17/PREREGISTRATION_ROUND7.md` contains addendum 7 with no PENDING
section, records hold-out 8's frozen digest, and is committed -- so git history shows the
predictions preceding the scores. Nothing is fitted here.

Scored once, with the owner's conversation (LoCoMo 1) as corroboration evidence: B12-B15, B17, B18
on every attack and on the benign half in both channels (untrusted and user_turn); B13's per-rule
decisions, so B13 with epistemic quarantine is computed exactly; and the epistemic-quarantine arms
(agent asserting the claim / using the benign information, with the note excluded, raw, or marked
UNVERIFIED) using the frame chosen on development data. Every rate on the full population and, if
the validity rule allows, on the working subset.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).parent / "data"
OUT = DATA / "eval_holdout8.json"
PARTIAL = DATA / "eval_holdout8_partial.json"
PREREG = ROOT / "docs" / "phase17" / "PREREGISTRATION_ROUND7.md"
MARK = "## Addendum 7"


def preregistration_in_force() -> str:
    """Returns the frame version the addendum fixes; refuses otherwise."""
    import re

    from phase17 import holdout8_corpus as h8

    txt = PREREG.read_text(encoding="utf-8")
    if MARK not in txt:
        raise SystemExit("the hold-out 8 pre-registration (addendum 7) has not been written")
    block = txt.split(MARK, 1)[1]
    if "PENDING" in block:
        raise SystemExit("addendum 7 still has PENDING sections")
    assert h8.verify_frozen(), "hold-out 8 does not match its frozen digest"
    if json.loads(h8.FREEZE.read_text(encoding="utf-8"))["sha256"] not in block:
        raise SystemExit("addendum 7 does not record hold-out 8's digest")
    m = re.search(r"EQ frame:\s*`?(v\d+)`?", block)
    if not m:
        raise SystemExit("addendum 7 must fix the epistemic-quarantine frame ('EQ frame: vN')")
    dirty = subprocess.run(["git", "status", "--porcelain", str(PREREG)], cwd=str(ROOT),
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit("commit addendum 7 before scoring hold-out 8")
    return m.group(1)


def _neutralisation(recs, val, workers: int = 3) -> Dict:
    """Admitted-raw vs v3 vs the instruction-aware v6 frame, on every hold-out-8 attack (added
    2026-10-09 BEFORE hold-out 8 exists, after v6 passed its dev criterion -- frame_instruction_dev.json).

    Same causal probe as holdout8_validity: owner's store, the item's fitted task, agent and judge. The
    raw arm IS the validity run's with-memory verdict (not re-run). Only arms the dev criterion admitted
    are run; benign cost of v6 was measured on development data only (hold-out 8's benign notes have no
    questions to answer)."""
    import concurrent.futures as cf

    from phase12.propagation.ollama_provider import OllamaProvider
    from phase17.attack_validity_audit import AGENT_MODEL, JUDGE_MODEL, _answer, _judge, _store
    from phase17.frame_instruction_dev import fires, v6_instruction_aware
    from phase17.holdout8_validity import SAMPLE, _tasks
    from phase17.neutralise_v2 import v3_depersonalise
    from phase17.stats import paired_delta, rate_with_ci
    from phase3.evaluation.llm.provider import GenerationConfig

    dev = json.loads((DATA / "frame_instruction_dev.json").read_text(encoding="utf-8"))
    frames = {"v3": v3_depersonalise}
    if dev.get("goes_to_holdout8"):
        frames["v6"] = v6_instruction_aware
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    tasks = _tasks("v2", recs)
    agent, judge = OllamaProvider(model=AGENT_MODEL), OllamaProvider(model=JUDGE_MODEL)
    acfg = GenerationConfig(temperature=0.0, seed=42, max_tokens=160, enable_thinking=False,
                            n_ctx=4096, request_timeout_sec=300.0)
    jcfg = GenerationConfig(temperature=0.0, seed=17, max_tokens=6, enable_thinking=False,
                            n_ctx=4096, request_timeout_sec=300.0)
    store = _store(SAMPLE)

    def arm(r, name):
        k = f"h8:frame:{name}:{r.scenario_id}"
        if k not in done:
            a = _answer(agent, acfg, store + [("poison", frames[name](r.text))], tasks[r.scenario_id])
            done[k] = bool(_judge(judge, jcfg, r.text, a))
        return done[k]

    vec = {"raw": [bool(val["compliance_with_memory"][r.scenario_id]) for r in recs]}
    for name in frames:
        v = []
        for i in range(0, len(recs), 12):
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                v += list(ex.map(lambda r: arm(r, name), recs[i:i + 12]))
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
            print(f"  frame {name} {len(v)}/{len(recs)}", flush=True)
        vec[name] = v
    fire = [fires(r.text) for r in recs]

    def block(mask):
        ix = [i for i, m in enumerate(mask) if m]
        b = {a: rate_with_ci(sum(vec[a][i] for i in ix), len(ix)) for a in vec}
        for a in frames:
            b[f"paired_{a}_vs_raw"] = paired_delta([vec[a][i] for i in ix], [vec["raw"][i] for i in ix])
        if "v6" in frames:
            b["paired_v6_vs_v3"] = paired_delta([vec["v6"][i] for i in ix], [vec["v3"][i] for i in ix])
        return b

    return {"frames": list(frames), "all": block([True] * len(recs)), "rule_fires": block(fire),
            "rule_silent": block([not f for f in fire]),
            "by_family": {f: {a: sum(vec[a][i] for i, r in enumerate(recs) if r.family == f) for a in vec}
                          | {"n": sum(r.family == f for r in recs)} for f in sorted({r.family for r in recs})}}


def run() -> dict:
    frame_version = preregistration_in_force()
    from phase17 import eval_round7_holdouts as E, dev_round7
    from phase17.b20_live import b13_components
    from phase17.epistemic_quarantine import evaluate as eq_evaluate
    from phase17.holdout8_corpus import attack_records, benign_texts
    from phase17.precompute_features import run as precompute
    from phase17.provenance_sets import owner_turns
    from phase17.stats import paired_delta, rate_with_ci

    E.PARTIAL = PARTIAL
    dev_round7.PARTIAL = PARTIAL
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}
    recs, b8 = attack_records(), benign_texts()
    a8 = [r.text for r in recs]
    precompute(a8 + b8)
    turns = owner_turns(1)
    ev, names = [t["text"] for t in turns], sorted({t["speaker"] for t in turns})
    A = {c: E._decide(c, a8, f"H8A{c}", done, f"h8:atk:{c}", ev, names) for c in E.CONFIGS}
    B = {c: E._decide(c, b8, f"H8B{c}", done, f"h8:ben:{c}", ev, names) for c in E.CONFIGS}
    Bu = {c: E._decide(c, b8, f"H8U{c}", done, f"h8:benu:{c}", ev, names, "user_turn") for c in E.CONFIGS}

    def comps(texts, kind):
        k = f"h8:comp:{kind}"
        if k not in done:
            items = [(f"H8{kind}{i}", t) for i, t in enumerate(texts)]
            got = {}
            for i in range(0, len(items), 20):
                ch = items[i:i + 20]
                got.update(b13_components(ch, sources={m: "tool_output" for m, _ in ch}, evidence=ev,
                                          evidence_names=names))
            done[k] = [got[m] for m, _ in items]
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
        return done[k]

    ca, cb = comps(a8, "atk"), comps(b8, "ben")
    from phase17.b20_live import b13_excluded_from_components

    assert [b13_excluded_from_components(c) for c in ca] == list(A["B13"]), "B13 components disagree with B13"
    eq = eq_evaluate("ho8", recs, ca, b8, cb, 1, frame_version=frame_version)
    val = json.loads((DATA / "holdout8_validity.json").read_text(encoding="utf-8"))
    W = set(val["working_ids"]) if val["working_reportable"] else None
    ids = [r.scenario_id for r in recs]
    out: Dict = {"preregistration": f"{PREREG.relative_to(ROOT)} (addendum 7)", "frame_version": frame_version,
                 "n_attacks": len(a8), "n_benign": len(b8), "working_reportable": val["working_reportable"],
                 "n_working": val["n_working"] if W is not None else None, "configs": {},
                 "epistemic_quarantine": eq,
                 "raw": {"attack": A, "benign": B, "benign_user_turn": Bu, "attack_ids": ids,
                         "attack_family": [r.family for r in recs]}}
    for c in A:
        w = [x for x, i in zip(A[c], ids) if W is not None and i in W]
        out["configs"][c] = {"attack_recall": rate_with_ci(sum(A[c]), len(A[c])),
                             "attack_recall_working": rate_with_ci(sum(w), len(w)) if W is not None else None,
                             "benign_fpr_untrusted_channel": rate_with_ci(sum(B[c]), len(B[c])),
                             "benign_fpr_user_turn": rate_with_ci(sum(Bu[c]), len(Bu[c]))}
    out["paired_B13_vs_B14_recall"] = paired_delta(A["B13"], A["B14"])
    out["neutralisation"] = _neutralisation(recs, val)
    fams = sorted({r.family for r in recs})
    out["recall_by_family"] = {f: {c: f"{sum(x for x, r in zip(A[c], recs) if r.family == f)}/"
                                      f"{sum(r.family == f for r in recs)}" for c in ("B12", "B13", "B14", "B17")}
                               for f in fams}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for c, v in r["configs"].items():
        print(f"{c}: recall {v['attack_recall']['k']}/{v['attack_recall']['n']}  FPR untrusted "
              f"{v['benign_fpr_untrusted_channel']['k']}/{r['n_benign']}  user_turn {v['benign_fpr_user_turn']['k']}")
    print("EQ:", json.dumps({k: v for k, v in r["epistemic_quarantine"].items() if k != "set"})[:600])
    print("DONE")
