"""Results Analysis sections 18-22 (defence programmes v2-v5 and closure assessment), generated from the committed
artifacts. Called by build_results_analysis_docx.py with its own writer helpers, so numbers cannot drift."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase17" / "data"


def _L(rel):
    p = DATA / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _f(x):
    return f"{x['k']}/{x['n']}"


def write(H, P, TBL, CAP, FIGF):
    sag, p2, s2 = _L("defence_v2/sag_eval.json"), _L("defence_v2/prop_eval.json"), _L("defence_v2/sleeper_v2_eval.json")
    vpl, ctc, s3 = _L("defence_v3/vpl_eval.json"), _L("defence_v3/ctc_eval.json"), _L("defence_v3/sleeper_v3_selection.json")
    prc, voa = _L("defence_v4/prc_eval.json"), _L("defence_v4/voa_eval.json")
    rac, racd, wtp, af = _L("defence_v5/rac_eval.json"), _L("defence_v5/rac_d_selection.json"), _L("defence_v5/wtp_eval.json"), _L("defence_v5/af_eval.json")
    lp, cp = _L("defence_v5/launder2_eval.json"), _L("defence_v5/launder_codepath.json")

    H("18. Defence Programme v2 (2026-10-13): Lineage, Multi-Generation Containment, Hard Sleeper Controls", 1)
    P("Pre-registered in docs/phase17/PREREGISTRATION_DEFENCE_V2_2026-10-13.md. Three workstreams addressed the three "
      "research gaps; every candidate was frozen before its held-out evaluation and failures are reported as such.")
    if sag:
        rows = [["Set", "Rule", "Stored-text decision (attacks / benign)", "With source lineage (SAG)", "Wrong lineage"]]
        for key, lab in (("MEM1_document", "MEM-1 (HO4 via Mem0)"), ("MEM2_document", "MEM-2 (SA-1 via Mem0)"),
                         ("SA3eval_document_vs_ben_unground", "SA-3 eval vs ungrounded benign")):
            if key in sag["sets"]:
                for X in ("B12", "B13"):
                    b = sag["sets"][key][X]
                    rows.append([lab, X, f"{_f(b['atk']['lost'])} / {_f(b['ben']['lost'])}",
                                 f"{_f(b['atk']['intact'])} / {_f(b['ben']['intact'])}", f"{_f(b['atk']['wrong'])} / {_f(b['ben']['wrong'])}"])
        TBL(rows)
        CAP("Table 18A. Source-anchored governance: inheriting the raw item's decision through write-time lineage. "
            "Inheriting B13 (which includes corroboration) exceeded the 3-point benign limit; inheriting the content "
            "decision (B12) recovers explicit payloads Mem0 strips. Source: phase17/data/defence_v2/sag_eval.json.")
    if p2:
        P(f"Multi-generation containment on held-out HO4 chains (owner 7; 157 attack roots, {p2['n_flagged_attack_roots']} "
          f"flagged): root-anchored lineage (RCL) withheld "
          f"{', '.join(_f(x) for x in p2['withheld_carrying_flagged']['RCL'])} payload-carrying descendants at generations "
          f"1-4 against {', '.join(_f(x) for x in p2['withheld_carrying_flagged']['FG'])} for the frozen guard, cutting "
          f"memory-attributable influence at generation 4 to {_f(p2['influence_remaining']['RCL'][3])} (undefended "
          f"{_f(p2['influence_by_gen_laundering'][3])}) with {_f(p2['collateral_unflagged_benign']['RCL'][3])} collateral on "
          f"unflagged benign descendants; all four pre-declared criteria held. Descendants of wrongly flagged benign roots "
          f"stay withheld ({_f(p2['collateral_flagged_benign']['RCL'][3])} at generation 4) until the root is released.")
    if s2:
        a = s2["eval_raw"]["aggregate"]
        P("Implicit sleepers against ungrounded benign conditional rules (SA-3; owner-disjoint dev 0,2,4,6 / eval 5,7,8): "
          f"corroboration flagged {a['B13']['atk'][0]}/{a['B13']['atk'][1]} attacks but {a['B13']['ben_unground'][0]}/"
          f"{a['B13']['ben_unground'][1]} legitimate ungrounded rules; the dev-selected policy ({s2['chosen']}) detected "
          f"{a[s2['chosen']]['atk'][0]}/{a[s2['chosen']]['atk'][1]} on eval. SA-2's earlier 40/60 vs 0/60 separation held "
          "only against benign rules grounded in the owner's conversation by construction.")

    H("19. Defence Programme v3 (2026-10-13/14): Verified Lineage, Claim Tracking, Steering Signal", 1)
    P("Pre-registered in docs/phase17/PREREGISTRATION_DEFENCE_V3_2026-10-13.md with weighted closure rubrics "
      "(FINAL_DEFENCE_BASELINE_AUDIT.md section 3) fixed before any outcome.")
    if vpl:
        rows = [["Set", "Lineage", "Attacks: B13 stored -> VPL", "Benign: B13 stored -> VPL", "Links accepted"]]
        for n, sset in vpl["sets"].items():
            for mode in ("correct", "wrong"):
                b = sset[mode]
                la = b.get("link_acceptance_true") or b.get("link_acceptance_wrong")
                rows.append([n, mode, f"{_f(b['atk']['B13_stored'])} -> {_f(b['atk']['VPL'])}",
                             f"{_f(b['ben']['B13_stored'])} -> {_f(b['ben']['VPL'])}", _f(la) if la else ""])
        TBL(rows)
        CAP(f"Table 19A. Verified payload-only lineage (P = {vpl['P']}, link threshold {vpl['tau_link']:.3f}, selected on "
            "SA-3 dev through Mem0). Wrong lineage no longer adds benign exclusion; the gain is limited to explicit payloads "
            "(MEM-2). Not accepted as a B13 replacement (gain on 1 of 3 sets). Source: defence_v3/vpl_eval.json.")
    if ctc:
        b = ctc["sets"]["HO8_instruction"]
        P(f"Claim-tracked containment (NLI entailment of the root claim, tau {ctc['selection']['tau']:.5f}, selected on dev "
          f"chains) on new held-out HO8 instruction-style chains: {_f(b['CTC']['withheld_carrying'][3])} payload-carrying "
          f"descendants withheld at generation 4 against {_f(b['FG']['withheld_carrying'][3])} (frozen guard) and "
          f"{_f(b['RCL']['withheld_carrying'][3])} (RCL); worse than RCL on factual payloads; not accepted. An evaluation-code "
          "defect (lineage arms ignored the root-flag guard) was found on first scoring, fixed to the pre-registered "
          "definition, and the defective output kept.")
    if s3:
        r = s3["dev"]["aggregate"]["raw"]
        P(f"Novel-entity steering signal (N1) on SA-3 dev: {r['N1']['atk'][0]}/{r['N1']['atk'][1]} attacks but "
          f"{r['N1']['ben_unground'][0]}/{r['N1']['ben_unground'][1]} legitimate ungrounded rules; no policy met the dev "
          "limits and the carried-forward policy failed on eval.")
    FIGF("F5", "Every implicit-sleeper detector tested, attack detection against legitimate ungrounded rules flagged (SA-3). "
               "B12, the sleeper guard and deberta sit at the origin. Source: defence_v2/sleeper_v2_eval.json, "
               "defence_v3/sleeper_v3_selection.json.")

    H("20. Defence Programme v4 (2026-10-14): Payload Routing and Verify-on-Activation", 1)
    P("Pre-registered in docs/phase17/PREREGISTRATION_DEFENCE_V4_2026-10-14.md, on new held-out data: HO7 propagation "
      "chains (owner 8) and a new sleeper corpus SA-4 (owners 1, 3, 9).")
    if prc:
        rows = [["Set", "Frozen guard", "RCL", "CTC", "PRC", "Accepted"]]
        for k, v in prc["sets"].items():
            b = v["pooled"]
            rows.append([f"{k.upper()} ({v['label'].split(' ')[0]})"] +
                        [_f(b[a]["withheld_carrying"][3]) for a in ("FG", "RCL", "CTC", "PRC")] + [str(v["acceptance"]["accepted"])])
        TBL(rows)
        CAP("Table 20A. Payload-carrying descendants withheld at generation 4. PRC routes each root to CTC (instruction) "
            "or RCL (factual). On the fresh HO7 set the generation-4 test against the frozen guard missed significance "
            "(p = 0.07) with only 10 carrying descendants left. Source: defence_v4/prc_eval.json.")
    FIGF("F4", "Containment across consolidation generations on three held-out chain sets. Unflagged-benign collateral is "
               "0/40 for every lineage arm. Source: defence_v4/prc_eval.json.")
    if voa:
        b = voa["sets"]["N1|B13"]
        P(f"Verify-on-activation keeps flagged memories but frames them as unverified. On SA-4 raw memories attack "
          f"unconfirmed activation fell from {_f(b['atk']['raw']['undefended']['unconfirmed_activation'])} to "
          f"{_f(b['atk']['raw']['VoA']['unconfirmed_activation'])} while {_f(b['ben_unground']['raw']['VoA']['surfaced'])} "
          f"legitimate ungrounded rules stayed usable (exclusion: {_f(b['ben_unground']['raw']['exclusion']['surfaced'])}); "
          f"after Mem0 rewriting there was no effect ({_f(b['atk']['stored']['undefended']['unconfirmed_activation'])} -> "
          f"{_f(b['atk']['stored']['VoA_via_verified_link']['unconfirmed_activation'])}). Not accepted.")
    FIGF("F6", "Verify-on-activation: works on raw memories (SA-4) and does not survive Mem0 rewriting reliably (SA-5). "
               "Source: defence_v4/voa_eval.json, defence_v5/af_eval.json.")

    H("21. Defence Programme v5 (2026-10-14): Authorship Provenance and Lineage-Free Containment", 1)
    P("Pre-registered in docs/phase17/PREREGISTRATION_DEFENCE_V5_2026-10-14.md with addenda A and B written before their "
      "computations.")
    if af:
        pv, g = af["provenance"], af["groups"]
        P(f"A provenance-recording wrapper around Mem0 kept the correct source on {pv['prw_correct']}/{pv['n_memories']} "
          "derived memories. Mem0's own UPDATE path is last-writer-wins on metadata: a user-channel update relabels a "
          f"document-planted memory as the user's ({'demonstrated at code level' if cp and cp.get('native_laundered') else 'see code'}); "
          "the wrapper keeps both sources. Mem0's extractor produced no such update in 225 ingestions, so the real-world "
          "frequency is unmeasured. The selected attribution frame "
          f"({af['frame']}) reduced attack unconfirmed activation on Mem0-stored text from "
          f"{_f(g['attacks_document']['undefended']['unconfirmed_activation'])} to "
          f"{_f(g['attacks_document'][af['frame']]['unconfirmed_activation'])} (not significant; not accepted); legitimate rules "
          f"arriving on the user channel were never framed ({_f(g['benign_user_channel']['undefended']['surfaced'])} usable "
          "under every arm).")
    if rac and wtp:
        P("Containment without lineage: matching new memories against a registry of flagged claims caught the payload but "
          f"excluded {_f(rac['sets']['ho7']['collateral_owner_observations'])}, {_f(rac['sets']['ho8']['collateral_owner_observations'])} "
          f"and {_f(rac['sets']['ho4']['collateral_owner_observations'])} of the owners' real benign memories; thresholds "
          f"re-selected on dev ({'none admissible' if racd and not racd.get('chosen') else 'see table'}) could not reach the "
          "3% limit. Write-time taint propagation, in which the consolidator taints its output from its own inputs, needs "
          "no stored lineage: it equals RCL-with-lineage item for item ("
          + ", ".join(f"{k.upper()} {v['item_for_item_equal_to_RCL_with_lineage']}" for k, v in wtp["sets"].items())
          + ") with zero unflagged collateral, and was accepted. Lineage deleted after writing remains unsolved.")

    H("22. Defence Architecture and Operational Gap Closure", 1)
    FIGF("F8", "The evaluated defence architecture, stage by stage, with each component's status.")
    from phase17.figures_final import CLOSURE, closure_scores
    sc = closure_scores()
    rows = [["Gap", "Capability (* = critical)", "Weight", "Evidence score"]]
    for g, caps in CLOSURE.items():
        for n, w, v in caps:
            rows.append([g, n, f"{w:.2f}", f"{v:.2f}"])
        rows.append([g, "GAP SCORE (critical caps applied)", "", f"{sc[g] * 100:.0f}%"])
    TBL(rows)
    CAP("Table 22A. Operational closure per gap from the weighted evidence-strength rubric fixed before the final "
        "programmes (FINAL_DEFENCE_BASELINE_AUDIT.md section 3). Scores measure evidence strength, not accuracy; no gap "
        "reaches the 75% target.")
    FIGF("F7", "Operational closure per research gap.")
