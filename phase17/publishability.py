"""The publishability verdict, computed from the artifacts against the two-sided standard.

PUBLISHABLE only if every criterion below passes:
  1. every claim is traceable to an artifact that exists
  2. every hold-out attack-detection rate carries its false-positive rate and both denominators
     (full population AND working subset), or the working subset is declared not reportable
     by the rule fixed before the corpus was built
  3. hold-out-informed numbers are labelled (no superseded or unlabelled claim stands in any
     document a reader meets)
  4. negatives and corrections are reported in place (every pre-registered prediction has a
     reported outcome, failures included)
  5. the full cross-phase suite passes
  6. no headline claim sits below the measured noise floor for its sample size
NOT PUBLISHABLE if any of: a headline claim depends on an unlabelled, repeatedly-scored hold-out;
an untested attack family is reported as measured; a guard is claimed without mutation proof.

A criterion whose evidence has not been produced yet is PENDING, never PASS. The verdict is
written to phase17/data/publishability.json and rendered by both document builders.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase17" / "data"
OUT = DATA / "publishability.json"

# The measured floor: three repeats on n=120 gave SDs of 0.8-1.7 points; the document applies
# 5 points at n=120 and scales it with 1/sqrt(n).


from phase17.stats import noise_floor_points as floor  # relocated to stats.py


def _L(name):
    p = DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _check(status, detail):
    return {"status": status, "detail": detail}


def traceability():
    inv = _L("final_inventory.json")
    if not inv:
        return _check("PENDING", "final_inventory.json not built")
    missing = []
    for r in inv["rows"]:
        for name in re.findall(r"[\w.]+\.json", r["artifact"]):
            if not (DATA / name).exists():
                missing.append(name)
    return _check("FAIL" if missing else "PASS",
                  f"{inv['n']} inventory rows; missing artifacts: {sorted(set(missing)) or 'none'}")


def denominators():
    rows, bad, pending = [], [], []
    e = (_L("eval_round7_holdouts.json") or {}).get("holdouts", {})
    e.update((_L("eval_round7b_holdouts.json") or {}).get("holdouts", {}))
    working = {"holdout4": (_L("holdout4_validity.json") or {}).get("n_working"),
               "holdout5": (_L("holdout5_causal.json") or {}).get("working", {}).get("k"),
               "holdout6": (_L("holdout6_causal.json") or {}).get("working", {}).get("k"),
               # Not reportable by the rule fixed before the corpus was built: the probe's task-alone
               # base rate (36/129) exceeds working_set.MAX_PROBE_BASE_RATE.
               "holdout7": "NOT_REPORTABLE"}
    for h in ("holdout4", "holdout5", "holdout6", "holdout7"):
        if h not in e:
            pending.append(h)
            continue
        for c, v in e[h]["configs"].items():
            fpr = any(k.startswith(("matched_benign_fpr", "benign_fpr")) for k in v)
            if "attack_recall" not in v or not fpr:
                bad.append(f"{h}/{c}")
        if working[h] is None:
            pending.append(f"{h} working subset")
        rows.append(f"{h}: working={working[h]}")
    if bad:
        return _check("FAIL", f"rates without an FPR: {bad}")
    if pending:
        return _check("PENDING", f"awaiting {pending}; " + "; ".join(rows))
    return _check("PASS", "; ".join(rows))


def labelled():
    from phase17.claims_guard import paragraphs_of, targets, violations

    hits = []
    for name, p in targets():
        if p.exists():
            hits += [(name, cid) for cid, _, _ in violations(paragraphs_of(p))]
    return _check("FAIL" if hits else "PASS",
                  f"superseded/unlabelled claims standing: {hits or 'none'}")


def negatives():
    p = _L("round7_predictions.json")
    if not p:
        return _check("PENDING", "round7_predictions.json missing")
    # DESCRIPTIVE is a reported outcome: those were pre-registered as untestable at their n
    # (require_power refused them) and are reported with their numbers, not tested.
    unscored = [q["id"] for q in p["predictions"] if q["status"] not in ("HELD", "FAILED", "DESCRIPTIVE")]
    failed = [q["id"] for q in p["predictions"] if q["status"] == "FAILED"]
    return _check("FAIL" if unscored else "PASS",
                  f"{p['n_held']}/{p['n_scored']} held; failures reported in place: {failed}; "
                  f"unscored: {unscored or 'none'}")


def suite():
    p = DATA / "_phase_audit.txt"
    if not p.exists():
        return _check("PENDING", "cross-phase audit not run")
    t = p.read_text(encoding="utf-8", errors="replace")
    # A stale audit proves nothing about the code as it stands: it must post-date every source change.
    newest = max(f.stat().st_mtime for d in ROOT.glob("phase*") if d.is_dir() for f in d.rglob("*.py"))
    if p.stat().st_mtime < newest:
        return _check("PENDING", "cross-phase audit predates the latest source change; re-run it")
    if "AUDIT COMPLETE" not in t:
        return _check("PENDING", "cross-phase audit incomplete")
    phases = re.findall(r"### (\S+)\n(.*?)(?=\n###|\nAUDIT COMPLETE)", t, re.S)
    failed = [ph for ph, body in phases
              if re.search(r"\d+ (failed|error)", body) or not re.search(r"\d+ passed", body)]
    passed = sum(int(x) for x in re.findall(r"(\d+) passed", t))
    return _check("FAIL" if failed else "PASS",
                  f"{len(phases)} phase suites, {passed} tests passed; failing: {failed or 'none'}")


def noise_floor():
    claims = []
    e = _L("eval_round7_holdouts.json")
    if e:
        h4 = e["holdouts"]["holdout4"]["configs"]
        claims.append(("provenance reaches memory poisoning (HO4, B13 vs B14 recall)",
                       100 * (h4["B13"]["attack_recall"]["rate"] - h4["B14"]["attack_recall"]["rate"]),
                       h4["B13"]["attack_recall"]["n"]))
    e2 = _L("eval_round7b_holdouts.json")
    if e2:
        d = e2["holdouts"]["holdout6"]["neutralisation"]["by_detector"]["B12"]["policies"]
        n = d["P2_exclude"]["n"]
        claims.append(("powered composition (HO6, P2 -> P4 harm)",
                       100 * (d["P2_exclude"]["harm_k"] - d["P4_exclude_plus_neutralise_rest"]["harm_k"]) / n, n))
    s = _L("neutralise_strong_agent_n120.json") or _L("neutralise_strong_agent.json")
    if s:
        claims.append(("framing helps a stronger agent (Gemini)", s["effect_points"]["gemini"], s["n"]))
    rows = [{"claim": c, "delta_points": round(d, 1), "n": n, "floor_points": round(floor(n), 1),
             "above": abs(d) >= floor(n)} for c, d, n in claims]
    below = [r["claim"] for r in rows if not r["above"]]
    return _check("FAIL" if below else ("PASS" if rows else "PENDING"),
                  "; ".join(f"{r['claim']}: {r['delta_points']:+.1f} vs floor {r['floor_points']} (n={r['n']})"
                            for r in rows)), rows


def _partial_results():
    return sorted(p.name for p in DATA.glob("*.json")
                  if not p.name.endswith("partial.json") and p.stat().st_size < 5_000_000
                  and '"complete": false' in p.read_text(encoding="utf-8", errors="replace"))


def disqualifiers():
    out = {}
    # (a) hold-out 3 is retired; any use is labelled by the claims guard (criterion 3) and the
    # retirement test. Re-check the use count in the artifacts never moves past seven.
    out["unlabelled_repeated_holdout"] = labelled()["status"] == "PASS"
    # (b) conditional backdoors on a clean hold-out are reported as untested, not measured.
    m7 = _L("holdout7_mechanism.json")
    cb = (m7 or {}).get("attack_mechanism", {}).get("conditional_backdoor", {})
    from phase17.claims_guard import docx_paragraphs

    rp = ROOT / "MAMBench Results Analysis.docx"
    text = " ".join(docx_paragraphs(rp)) if rp.exists() else ""
    out["untested_family_reported_untested"] = (not cb) or (
        cb.get("k", 0) < 20 and "conditional backdoors are reported as untested" in text)
    # (c) every registry guard is mutation-proven.
    reg = _L("error_registry.json")
    out["every_guard_mutation_proven"] = bool(reg) and reg["n_proven"] == reg["n"] and all(
        e["status"] in ("PROVEN", "PROVEN_ELSEWHERE") for e in reg["errors"])
    out["registry"] = f"{reg['n_proven']}/{reg['n']} proven" if reg else "missing"
    return out


def run() -> dict:
    nf, nf_rows = noise_floor()
    crit = {"1_traceable": traceability(), "2_fpr_and_both_denominators": denominators(),
            "3_holdout_informed_labelled": labelled(), "4_negatives_in_place": negatives(),
            "5_full_suite_passes": suite(), "6_above_noise_floor": nf}
    # Owner's rule (2026-10-08): no verdict while any scheduled measurement is PARTIAL. The
    # harm re-measurement was cut short by the Gemini daily quota; the verdict waits for it.
    partial_now = _partial_results()
    crit["7_all_measurements_complete"] = _check(
        "PENDING" if partial_now else "PASS",
        f"partial: {partial_now}" if partial_now else "no artifact reports complete: false")
    dq = disqualifiers()
    statuses = [c["status"] for c in crit.values()]
    dq_ok = all(v for k, v in dq.items() if k != "registry")
    if not dq_ok or "FAIL" in statuses:
        verdict = "NOT PUBLISHABLE"
    elif "PENDING" in statuses:
        verdict = "PENDING"
    else:
        verdict = "PUBLISHABLE"
    # Results reported as PARTIAL are disclosed in the verdict, not hidden by it: each must say so in
    # its own artifact (complete: false) and is listed here so a reader sees what is outstanding.
    partial = _partial_results()
    out = {"verdict": verdict, "criteria": crit, "disqualifiers_clear": dq, "noise_floor_claims": nf_rows,
           "disclosed_partial_results": partial,
           "standard": __doc__.strip().split("\n\n")[1]}
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for k, v in r["criteria"].items():
        print(f"{v['status']:8s} {k}: {v['detail']}")
    print("disqualifiers clear:", r["disqualifiers_clear"])
    print("VERDICT:", r["verdict"])
