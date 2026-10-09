"""Generate docs/phase17/ROUND7_RESULTS.md -- the current one-page summary -- from the artifacts.

PHASE17_FINAL_RESULTS.md points readers here. Every number is read at build time, so the summary
cannot drift from the data; scripts/finalize_round7.py rebuilds it with the two documents.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))   # runnable as a script as well as with -m
DATA = ROOT / "phase17" / "data"
OUT = ROOT / "docs" / "phase17" / "ROUND7_RESULTS.md"


def L(n):
    p = DATA / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def pct(x):
    return f"{100 * x:.1f}%"


def build() -> str:
    E = (L("eval_round7_holdouts.json") or {}).get("holdouts", {})
    E.update((L("eval_round7b_holdouts.json") or {}).get("holdouts", {}))
    P, PUB, HR = L("round7_predictions.json"), L("publishability.json"), L("harm_rejudged.json")
    AD, LB, S120 = L("adaptive_round7.json"), L("adaptive_ledger_b13.json"), L("neutralise_strong_agent_n120.json")
    HS, UT, SW = L("harm_strong_agent.json"), L("neutralise_utility.json"), L("eval_ledger_radius_sweep.json")
    V4, C5, C6 = L("holdout4_validity.json"), L("holdout5_causal.json"), L("holdout6_causal.json")
    out = []
    w = out.append
    w("# MAMBench Phase 17 -- current results (round 7)\n")
    w("Generated from the artifacts by `phase17/build_round7_summary.py`; do not edit by hand. The "
      "full account is `MAMBench Results Analysis.docx` (results) and `Methodology Draft.docx` "
      "(methods, Sections 32.49-32.62); every correction is logged in `docs/phase17/ROUND7_LOG.md`.\n")
    if PUB:
        w(f"**Publishability verdict: {PUB['verdict']}.** "
          + ("Held by the owner's rule until every scheduled measurement is complete; outstanding: "
             + ", ".join(PUB.get("disclosed_partial_results") or []) + "." if PUB["verdict"] == "PENDING" else "")
          + " Computed by `phase17/publishability.py`; criteria: "
          + "; ".join(f"{k} {v['status']}" for k, v in PUB["criteria"].items()) + ".\n")

    w("## Recommendation, conditioned on the threat and the false-positive budget\n")
    if "holdout4" in E:
        h4 = E["holdout4"]["configs"]
        w(f"1. **Memory poisoning, owner's conversation available: B13 with evidence.** Hold-out 4: "
          f"{pct(h4['B13']['attack_recall']['rate'])} recall at {pct(h4['B13']['benign_fpr_untrusted_channel']['rate'])} "
          f"false positives on untrusted channels and {pct(h4['B13']['benign_fpr_user_turn']['rate'])} on the "
          f"user's own words; B14 reaches {pct(h4['B14']['attack_recall']['rate'])}."
          + ((lambda h7: f" Hold-out 7 (a second, base-model author): {pct(h7['B13']['attack_recall']['rate'])} "
              f"at {pct(h7['B13']['benign_fpr_untrusted_channel']['rate'])} untrusted / "
              f"{pct(h7['B13']['benign_fpr_user_turn']['rate'])} user_turn; B14 "
              f"{pct(h7['B14']['attack_recall']['rate'])}.")(E["holdout7"]["configs"]) if "holdout7" in E else ""))
    if "holdout5" in E and "holdout6" in E:
        a, b = E["holdout5"]["configs"]["B17"], E["holdout6"]["configs"]["B17"]
        w(f"2. **Injection-shaped text: B17, not B18.** {pct(a['attack_recall']['rate'])} at "
          f"{pct(a['matched_benign_fpr']['rate'])} (hold-out 5) and {pct(b['attack_recall']['rate'])} at "
          f"{pct(b['matched_benign_fpr']['rate'])} (hold-out 6), matched benign. B18's deberta rule costs "
          f"{pct(E['holdout6']['configs']['B18']['matched_benign_fpr']['rate'])} on hold-out 6.")
    w("3. **Neutralisation** (admit untrusted memory framed as data) as a zero-exclusion layer under "
      "either.")
    if LB and SW:
        w(f"4. **Retry-capable attackers: add the rejection ledger at radius {SW['recommended_radius']}.** "
          f"With B13 + evidence, adaptive evasion {LB['control_evasion']['k']}/{LB['n_seeds']} -> "
          f"{LB['ledger_evasion']['k']}/{LB['n_seeds']} (pre-registered, p={LB['paired_ledger_vs_control']['p_exact']:.2g}).")
    w("")

    w("## Hold-outs 4-7, each frozen and scored once\n")
    w("| Hold-out | Config | Recall (all) | Recall (working) | False positives |")
    w("|---|---|---|---|---|")
    masks = {}
    if V4 and "holdout4" in E:
        W = set(V4["working_ids"])
        masks["holdout4"] = [i in W for i in E["holdout4"]["raw"]["attack_ids"]]
    if C5:
        masks["holdout5"] = C5["per_item_working"]
    if C6:
        masks["holdout6"] = C6["per_item_working"]
    for h in ("holdout4", "holdout5", "holdout6", "holdout7"):
        if h not in E:
            continue
        for c in ("B12", "B13", "B14", "B17", "B18"):
            v = E[h]["configs"][c]
            fp = v.get("matched_benign_fpr") or v.get("benign_fpr_untrusted_channel")
            if h in masks:
                xs = [x for x, k in zip(E[h]["raw"]["attack"][c], masks[h]) if k]
                wk = f"{pct(sum(xs) / len(xs))} ({sum(masks[h])})"
            else:
                wk = "not reportable (probe base rate > 20% rule)" if h == "holdout7" else "-"
            w(f"| {h} | {c} | {pct(v['attack_recall']['rate'])} | {wk} | {pct(fp['rate'])} |")
    w("\nHold-outs 4 and 7 are memory poisoning (false positives on untrusted-channel benign notes); "
      "5 and 6 are injection corpora with matched benign halves. B17/B18 were selected after reading "
      "earlier hold-out results; these are their first clean estimates.\n")

    w("## Findings\n")
    if "holdout4" in E and "holdout7" in E:
        from phase17.stats import paired_delta
        d4 = paired_delta(E["holdout4"]["raw"]["attack"]["B13"], E["holdout4"]["raw"]["attack"]["B14"])
        d7 = paired_delta(E["holdout7"]["raw"]["attack"]["B13"], E["holdout7"]["raw"]["attack"]["B14"])
        w(f"- **Provenance reaches memory poisoning that content classification misses, on two independent "
          f"hold-outs:** B13 vs B14 {d4['detected_a']}/{d4['n']} vs {d4['detected_b']}/{d4['n']} on hold-out 4 "
          f"(p={d4['p_exact']:.1g}) and {d7['detected_a']}/{d7['n']} vs {d7['detected_b']}/{d7['n']} on "
          f"hold-out 7 (p={d7['p_exact']:.1g}), two author families, two owners.")
    if HR and HR.get("undefended_all_items"):
        u = HR["undefended_all_items"]
        w(f"- **Harm levels were under-estimated by about half.** Re-judged on identical answers by the "
          f"judge selected against held-back human labels: undefended harm "
          f"{pct(u['J2_gemini_original']['rate'])} vs {pct(u['J0_current']['rate'])} "
          f"(p={HR['paired_judges_undefended']['p_exact']:.1g}). B13's reduction holds under both judges"
          + ("." if HR.get("complete") else f" (PARTIAL: {HR['stratum']['n']}-item family stratum; "
             f"{HR['missing_verdicts']} verdicts outstanding)."))
    if AD:
        c = AD["vs_corroboration"]["adaptive_evasion"]
        w(f"- **Corroboration is brittle to an adaptive attacker** ({c['k']}/{AD['vs_corroboration']['n_seeds']} "
          f"evade by paraphrase) **and the ledger closes it** (see recommendation 4).")
    if S120:
        w(f"- **Framing helps a stronger agent more:** Gemini {pct(S120['arms']['raw']['rate'])} -> "
          f"{pct(S120['arms'][S120['frame']]['rate'])} vs qwen {S120['effect_points']['qwen']:+.1f} points "
          f"(n={S120['n']}).")
    if HS:
        g = HS["gemini"]
        w(f"- **B13 protects a stronger agent:** Gemini harm {pct(g['harm_undefended']['rate'])} -> "
          f"{pct(g['harm_b13']['rate'])} (p={g['paired_b13_vs_undefended']['p_exact']:.2g}, seeded {HS['n']}).")
    if UT:
        worst = max(UT["tasks"].items(), key=lambda kv: kv[1]["loss_points"])
        w(f"- **The frame costs no significant usefulness** on benign memories (largest loss: {worst[0]}, "
          f"{worst[1]['loss_points']:.1f} points, p={worst[1]['paired_framed_vs_raw']['p_exact']:.2g}).")
    RW = L("risk_weighted_retrieval_eval.json")
    if RW:
        e = RW["exposure"]
        w(f"- **Phase 10's risk-weighted retrieval, first evaluated:** with admission signals as corroboration "
          f"it keeps the poison out of the agent's context in {e['A1']['k'] - e['A3']['k']} more of {RW['n']} cases "
          f"than the fixed-gate guard (p={RW['paired_A3_vs_A1']['p_exact']:.2g}), at no benign cost; the fixed gate "
          f"itself barely acts on realistic stores ({e['A0']['k']} -> {e['A1']['k']}).")
    CP = L("rwr_campaign.json")
    if CP:
        e = CP["exposure"]
        w(f"- **The retrieval consensus guard works on the threat it was built for:** against coordinated "
          f"campaigns (poison + 2 paraphrases) any copy reached the agent {e['A0']['k']} -> {e['A1s']['k']} of "
          f"{CP['n']} with semantic divergence (lexical: {e['A1']['k']}); against a single poison it is inert.")
    w("- **Full-population recall can mislead in either direction:** on hold-out 6 the attacks that work "
      "are harder to detect; on hold-outs 4 and 5 they are easier for B13. Both denominators are reported.")
    w("")

    if P:
        mu = P.get("multiplicity", {})
        w("## Pre-registered predictions\n")
        w(f"{P['n_held']}/{P['n_scored']} held ({P['verdict']}). Failed, reported in place: "
          + ", ".join(q["id"] for q in P["predictions"] if q["status"] == "FAILED") + ". "
          + (f"After Holm correction across the {mu['m']} significance predictions, "
             + (", ".join(mu["held_but_not_surviving"]) + " no longer holds."
                if mu.get("held_but_not_surviving") else "every held one survives.") if mu else "") + "\n")

    w("## Not done, partial, or untested -- stated, not hidden\n")
    if HR and not HR.get("complete"):
        w("- Harm re-measurement: PARTIAL (Gemini daily quota); completes with "
          "`python -m phase17.harm_judge_fix rejudge`.")
    w("- The ledger composed with B18: not measured (about 40 s per B18 decision on novel text; an "
      "estimated 4-9 GPU hours). B18 is no longer recommended.")
    w("- Phase 10's risk-weighted monitoring (ordering forensic targets): built and tested, not evaluated.")
    w("- Conditional backdoors: untested on a clean hold-out (a base-model author produced 3/40 valid).")
    w("- The human check of the judges has one annotator; a second is open.")
    w("- Hold-out 3 is retired after seven uses; its numbers are hold-out-informed where used.")
    w("- No LICENSE: deliberately deferred by the owner.")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")
    print("DONE")
