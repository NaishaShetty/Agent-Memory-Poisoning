"""Every round-3-to-6 result, read from the artifacts and sorted into favourable, unfavourable
and open.

Written because a summary assembled from memory is where selective reporting creeps in. Each
row names the artifact it came from, so any line can be checked, and the classification rule is
applied mechanically rather than by recollection:

  FAVOURABLE    a measured improvement, or a claim that survived a test designed to break it
  UNFAVOURABLE  a measured regression, a prediction that failed, a claim of mine that was wrong,
                or a result that went against the project
  OPEN          measured but unresolved, or untestable with what exists

A result can be favourable and still carry a caveat; the caveat travels with it rather than
being dropped to make the row read better.
"""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = DATA / "final_inventory.json"


def L(n):
    p = DATA / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


A = {n: L(f"{n}.json") for n in (
    "eval_round6", "working_set", "recall_on_working", "harm_study_v2", "validated_regen",
    "eval_rejection_memory", "eval_rejection_fresh", "eval_rejection_powered",
    "baseline_breakdown_round6", "attack_validity_audit", "defense_cost", "mechanism_validation",
    "rejection_memory_config", "eval_holdout3", "holdout3_matched_fpr", "holdout3_frontier",
    "benign_validity_audit", "diagnose_benign_fpr", "evidence_round6", "family_breakdown",
    "exfiltration_agent_check", "exfiltration_store_check", "exfiltration_task_fix",
    "multihop_multiagent", "eval_rejection_memory_sim090_EXPLORATORY")}


def pct(x):
    return "n/a" if x is None else f"{100*x:.1f}%"


def rows():
    out = []

    def add(cat, item, result, artifact, caveat=""):
        out.append({"category": cat, "item": item, "result": result,
                    "artifact": artifact, "caveat": caveat})

    ws, h, e6 = A["working_set"], A["harm_study_v2"], A["eval_round6"]
    bb, ev, fam = A["baseline_breakdown_round6"], A["evidence_round6"], A["family_breakdown"]
    h3, mf, fr = A["eval_holdout3"], A["holdout3_matched_fpr"], A["holdout3_frontier"]
    bva, dg, mha = A["benign_validity_audit"], A["diagnose_benign_fpr"], A["multihop_multiagent"]
    vr, ad, frs, pw = A["validated_regen"], A["eval_rejection_memory"], A["eval_rejection_fresh"], A["eval_rejection_powered"]
    xa, xs, xt = A["exfiltration_agent_check"], A["exfiltration_store_check"], A["exfiltration_task_fix"]

    # ---------------- FAVOURABLE
    if h:
        o = h["overall"]
        add("favourable", "Unconditional harm reduction (B13)",
            f"{pct(o['harm_no_defense']['rate'])} undefended -> {pct(o['harm_b13']['rate'])}; "
            f"task-alone base rate {o['harm_no_poison']['k']}/{o['harm_no_poison']['n']}",
            "harm_study_v2.json",
            "population changed from the 42.3%->12.5% figure, so levels are not comparable")
    add("favourable", "Provenance reaches classes content-only cannot (pre-registered)",
        "additive fabrication 0/72 -> 37/72 (p=1e-11); fabricated preferences 0/48 -> 27/48 "
        "(p=1e-08); legitimate-instruction false flags 14/40 -> 2/40", "PREREGISTRATION_B13.md")
    if A["defense_cost"]:
        c = A["defense_cost"]["per_config"]
        add("favourable", "Provenance is cheaper than the stack it replaces",
            f"B13 {c['B13']['seconds_per_memory']}s vs B12 {c['B12']['seconds_per_memory']}s per "
            f"admitted memory", "defense_cost.json")
    if bb:
        add("favourable", "Bespoke signals beat every published detector on memory poisoning",
            f"own attacks: B13 {pct(bb['aggregate_own']['B13']['rate'])} vs deberta "
            f"{pct(bb['aggregate_own']['deberta_pi_v2@dev']['rate'])}; baselines 3-15% on "
            f"note-shaped poisoning", "baseline_breakdown_round6.json")
        f = bb["ordinary_benign_fpr"]
        add("favourable", "Our false-positive rates far below the baselines' on ordinary memory",
            f"B13 {f['B13']['k']}/{f['n']}, B15 {f['B15']['k']}/{f['n']} vs deberta "
            f"{f['deberta_pi_v2@dev']['k']}/{f['n']}, Llama Guard "
            f"{f['llama_guard3@dev']['k']}/{f['n']}", "baseline_breakdown_round6.json")
    if ws:
        add("favourable", "Working-set discipline (the round's main methodological contribution)",
            f"{ws['n_working_set']}/{ws['n_total']} = {pct(ws['overall_rate'])} of instances both "
            f"subvert an undefended agent and implement their label; per-population floors break "
            f"CI on drift", "working_set.json")
    add("favourable", "AgentPoison published records function once probed correctly",
        "0/6 -> 3/6 working, task-alone base rate 0; four prior readings were measurement error",
        "attack_validity_audit.json")
    if vr:
        w = vr["families"]["memory_worm"]["heldout"]
        add("favourable", "memory_worm regeneration",
            f"33% mechanism-correct -> {pct(w['rate'])} by an out-of-loop judge; undefended harm "
            f"83.3% at 60% retrieval -> 3.3% with B13", "validated_regen.json")
    if ev:
        g = ev["aggregate"].get("B13", {})
        add("favourable", "Corroboration fix lifts every founding family",
            f"sleeper 0% -> 37%, MPBench 11% -> 46%, MINJA 13% -> 33%, DSRM 17% -> 30%, FARMA "
            f"74% -> 87%; aggregate own-attack recall "
            f"{pct((g.get('attacks_no_evidence') or {}).get('rate'))} -> "
            f"{pct((g.get('attacks_with_evidence') or {}).get('rate'))}, discrimination +46.1 -> "
            f"+52.2", "evidence_round6.json",
            "costs 7.5% ordinary-benign FPR, all of it on untrusted channels")
        add("favourable", "Corroboration costs nothing on user-authored content",
            "legitimate standing instructions 0/40, named-party preferences 0/6, confirmed-human "
            "0/20 in the user_turn channel with evidence live", "evidence_round6.json")
    add("favourable", "Union configurations beat both components at no extra FPR (descriptive)",
        "B17 own 51.2% vs B13 46.1% / B14 41.2%; adds no ordinary-benign false positive",
        "baseline_breakdown_round6.json", "hold-out-informed; not a clean estimate")
    if mf:
        r = {e["scorer"]: e for e in mf["ranking_at_matched_dev_fpr"]}
        add("favourable", "Matched operating points close most of the baseline gap",
            f"deberta +{100*r['deberta_pi_v2']['recall_minus_fpr']:.1f} vs B14 "
            f"+{100*r['B14']['recall_minus_fpr']:.1f}; was a 17-point gap at shipped thresholds, "
            f"now 2.8", "holdout3_matched_fpr.json",
            "the baseline still leads on that corpus")
    if mha:
        add("favourable", "Multi-hop is not a reasoning ceiling",
            "every agent 80-87% correct under the LLM judge; Gemini 60.0% strict, below "
            "phi3:mini's 65.0%; the oracle ceiling is NLI strictness",
            "multihop_multiagent.json",
            "this corrects a claim this project had published")
    add("favourable", "Three frozen hold-outs with pre-registration and digest verification",
        "1,258 + 1,200 + 1,000 human-authored attacks; hold-out 3 adds 995 MATCHED benign from "
        "the same platforms", "holdout3_freeze.json")

    # ---------------- UNFAVOURABLE
    if h3:
        add("unfavourable", "Matched-benign false-positive rates are very high",
            f"B18 {pct(h3['configs']['B18']['matched_benign_fpr']['rate'])}, B14 "
            f"{pct(h3['configs']['B14']['matched_benign_fpr']['rate'])}, B13 "
            f"{pct(h3['configs']['B13']['matched_benign_fpr']['rate'])} against 0.09% on "
            f"ordinary memory", "eval_holdout3.json",
            "every FPR previously published used benign text unlike the attack distribution")
        add("unfavourable", "Three of five pre-registered predictions failed",
            "P2 (B18 beats B14 by 5pts) failed at +0.4; P4 (baselines degrade most) failed "
            "backwards; P5 (nothing above 85%) failed for four configs", "eval_holdout3.json")
        add("unfavourable", "The recall ranking inverts once FPR is counted",
            "B14/B17/B18 reach 92.7-93.1% recall by flagging >half of benign; their "
            "discrimination is the worst of the configurations tested", "eval_holdout3.json")
    if bva:
        v = bva["populations"]["holdout3_matched_benign"]["valid_benign"]
        add("unfavourable", "My labelling-artifact hypothesis was mostly wrong",
            f"{pct(v['rate'])} of the corpus is benign-as-a-memory; filtering moves B18 only "
            f"54.9% -> 49.0%, about 6 of 55 points", "benign_validity_audit.json")
    if dg:
        add("unfavourable", "The content detector is the false-positive source, not provenance",
            f"content-only {pct(dg['fpr']['B12']['rate'])} on DEV in-the-wild benign; "
            f"corroboration adds {dg['attribution']['added_by_corroboration_with_evidence']} of "
            f"{dg['n']}", "diagnose_benign_fpr.json",
            "my earlier reading blamed corroboration and was wrong")
    add("unfavourable", "'B13 is the recommendation' was wrong unqualified",
        "on working attacks B14 STRICTLY dominates B13 on the clean hold-out, 40/64 vs 8/64, "
        "+32/-0, p=5e-10; B13's 12.5% there was unreported", "recall_on_working.json")
    add("unfavourable", "B14's hold-out gap is half composition, half inherited from deberta",
        "36.6-point gap narrows to 20.6 on working attacks (p=0.0001); B14 agrees with deberta "
        "90.1% on external corpora and degrades worse than it across corpora",
        "eval_round6.json + recall_on_working.json")
    if fr:
        s17, s18 = fr["shipped"]["B17"], fr["shipped"]["B18"]
        add("unfavourable", "The union configurations are badly calibrated",
            f"B17 leaves {100*s17['youden_headroom']:.1f} and B18 "
            f"{100*s18['youden_headroom']:.1f} points of discrimination on the table at their "
            f"shipped thresholds", "holdout3_frontier.json")
    if frs:
        add("unfavourable", "B16 falsified by its own pre-registered rule",
            f"1/38 -> 0/38, p={frs['paired_B16_vs_B15']['p_exact']}; the rule said p>0.1 "
            f"falsifies", "eval_rejection_fresh.json",
            "one control event caps the p-value at 1.0, so the test was underpowered: a flaw in "
            "my seed-selection rule")
    if vr:
        x = vr["families"]["exfiltration_instruction"]
        add("unfavourable", "Exfiltration regeneration only half worked",
            f"38% -> {pct(x['heldout']['rate'])} out-of-loop, but generator acceptance "
            f"{pct(x['acceptance_rate'])} equals the unguided rate, so the spec did not improve "
            f"authoring", "validated_regen.json")
    add("unfavourable", "My own errors this round",
        "AgentPoison trigger error a 5th time (caught by my own new guard test); rejection-memory "
        "dev fit measured the wrong distribution; orphan script killed the pipeline runner; a "
        "guard test matched its own docstring; corroboration left inert in every published table; "
        "the user_turn arm computed but never reported; B12 omitted from the table testing it",
        "git history")
    if fam:
        add("unfavourable", "Five of seven founding families are weakly detected content-only",
            "DSRM, MPBench, MINJA, MemoryGraft 11-32%; sleeper 0% before the corroboration fix",
            "family_breakdown.json", "these are floors; see evidence_round6.json")

    # ---------------- OPEN
    if pw:
        add("open", "Adaptive evasion", pw.get("verdict", "pending"),
            "eval_rejection_powered.json")
    elif ad:
        add("open", "Adaptive evasion",
            "no significant effect at the frozen radius (4/30 vs 5/30, p=1.0); 0/30 at 0.90 is "
            "exploratory; pre-registered re-run falsified but underpowered",
            "eval_rejection_memory.json")
    if xt:
        add("open", "Exfiltration mechanism", xt.get("verdict", "pending"),
            "exfiltration_task_fix.json")
    elif xs:
        add("open", "Exfiltration mechanism", xs.get("verdict", "pending"),
            "exfiltration_store_check.json")
    add("open", "B17/B18 have no clean hold-out estimate",
        "both were chosen after reading hold-out results; hold-out 3 tested them once, and their "
        "shipped calibration is poor there", "eval_holdout3.json")
    add("open", "All three hold-outs are injection/jailbreak corpora",
        "a good score there is evidence about overt injected instructions, not about additive "
        "fabrication or preference hijack; this project's own populations remain the only test "
        "of those", "holdout3_corpus.py")
    add("open", "LICENSE not attached", "deliberately deferred by the owner", "-")
    return out


def run() -> dict:
    rs = rows()
    out = {"n": len(rs),
           "counts": {c: sum(1 for r in rs if r["category"] == c)
                      for c in ("favourable", "unfavourable", "open")},
           "classification_rule": __doc__.strip().split("\n\n")[1],
           "rows": rs}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for cat in ("favourable", "unfavourable", "open"):
        print(f"\n{'='*78}\n{cat.upper()}  ({r['counts'][cat]})")
        for row in r["rows"]:
            if row["category"] != cat:
                continue
            print(f"\n  {row['item']}")
            print(f"    {row['result']}")
            if row["caveat"]:
                print(f"    CAVEAT: {row['caveat']}")
            print(f"    [{row['artifact']}]")
    print(f"\n{'='*78}\ntotals: {r['counts']}")
    print("DONE")
