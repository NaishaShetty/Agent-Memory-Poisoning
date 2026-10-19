"""Results Analysis section 24 / Methodology section 32.72 (Defence v7, 2026-10-15/17), generated from the v7 artifacts.
Called by build_results_analysis_docx.py and update_methodology_v7.py with their own writer helpers, so the two documents
cannot disagree. A sub-section whose artifact does not exist yet is written as 'in progress'."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase17" / "data" / "defence_v7"
UNG = ("ben_unground", "ben_future", "ben_unusual")


def _L(n):
    p = DATA / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _f(x):
    return f"{x['k']}/{x['n']}"


def _p(x):
    return f"{100 * x['k'] / x['n']:.1f}%" if x and x.get("n") else "n/a"


def _stored_only_ung():
    it = _L("g1_eval_sa7_items.json") or {}
    xs = [v for v in it.values() if v["kind"] in UNG and v.get("mem_gp")]
    return f"{sum(v['GP_excl'] for v in xs)}/{len(xs)}"


def blocks():
    g1, g2, g3, csd, cl = _L("g1_eval_sa7.json"), _L("g2_eval_ho10.json"), _L("g3_eval_sa7.json"), _L("g3_csd_eval.json"), _L("closure_v7.json")
    g1d, g3p, d2 = _L("g1_dev_sa7.json"), _L("g3_pilot_sa7dev.json"), _L("dcr2_dev.json")
    b = [("h", "24. Defence Programme v7 (2026-10-15/17): Graded Provenance, No-Decay Containment, Fresh Sleeper Test")]
    b.append(("p", "Pre-registered in docs/phase17/v7/SA7_PREREGISTRATION.md (addenda A-C) before any v7 data existed; the "
                   "pre-registration and every development selection were frozen by checksum (no git commit, at the owner's "
                   "request). v7 builds only new held-out data: SA-7 (640 sleeper, legitimate and high-impact notes; owners "
                   "1, 3, 5, 7, 8, 9 held out), MSD-7 (mixed-source documents), CSD-7 (80 coherent source documents) and HO10 "
                   "(727 propagation roots from owners never used for propagation). Gap 3 follows a separate brief: E is the "
                   "primary operating point, C AND K a secondary comparison, and document consistency, beneficiary familiarity, a "
                   "high-impact action gate and counterfactual confirmation are tested as additions."))
    b.append(("h2", "24.1 Design, data and integrity record"))
    b.append(("table", [["Set", "Construction", "Size", "Use"],
                        ["SA-7", "Gemini, SA-6 template and gates; 8 kinds incl. high-impact attacks and legitimate high-impact "
                                 "rules; SA-6 channel function", "640 notes (dev 256 / eval 384) + 40 user-relayed attacks",
                         "Gaps 1 and 3; frozen 0fba4e79"],
                        ["MSD-7", "explicit attack note + 2 legitimate notes per document", "120 documents", "Gap 1"],
                        ["CSD-7", "a coherent document with one inserted rule, as written or rewritten to fit", "80 documents",
                         "Gap 3 (secondary)"],
                        ["HO10", "HO9's generator, owners 0, 4, 6", "480 instruction (252 flagged), 129 factual (50 flagged), "
                                 "118 benign", "Gap 2; frozen 49af6aec"]]))
    b.append(("cap", "Table 24.1. New v7 data; no earlier set was re-used for confirmation."))
    b.append(("p", "Deviations and defects (recorded before the affected result was reported; defective outputs kept): (D0) two "
                   "development diagnostics wrote additions to v6 caches (moved to v7 caches; v6 files restored); (D1) SA-7 seed "
                   "values overlap SA-6's shifted by one owner (owner-seed pairs disjoint, near-duplicate blocking applies); (D3) "
                   "CSD-7 has 80 documents, not the 160 the pre-registration miscounted; (D4) Mem0 stored no memory for 110 of "
                   "880 jobs, mostly legitimate rules (40/80 unusual rules), so every benign rate is also reported on the "
                   "stored-only subset; (D5) the closure script first tested Gap 1.5's reduction in the wrong direction and was "
                   "fixed before any score was reported; (D6) v7's tests leaked re-pointed cache paths into v6's tests in a shared test "
                   "session (fixed with a restoring fixture; no result affected). The first lineage-recovery candidate (DCR) failed its development gate; "
                   "addendum B pre-registered DCR-2 before any HO10 chain existed."))
    if g1:
        s, m = g1["single_notes"], g1["msd"]
        b.append(("h2", "24.2 Gap 1: graded provenance (held-out)"))
        b.append(("p", "Graded provenance (GP) separates strong from weak evidence. An untrusted memory is excluded only when its "
                       "validly linked source claim (or, failing a link, its own text) is flagged by both B12 and the intent "
                       "judge; an untrusted memory flagged only by corroboration is kept and shown with the 'unverified, confirm "
                       "first' frame; user-channel memories are never excluded or framed. The rule was chosen on SA-6 development "
                       f"data and confirmed on SA-7 development data (explicit {_f(g1d['single_notes']['atk_explicit']['GP_excl'])}, "
                       f"ungrounded legitimate {_f(g1d['single_notes']['pooled_ungrounded']['GP_excl'])})." if g1d else ""))
        b.append(("table", [["SA-7 eval", "B13 on stored", "PCL (v6)", "GP excluded", "GP framed"],
                            ["Explicit attacks", _f(s["atk_explicit"]["B13s"]), _f(s["atk_explicit"]["PCL"]), _f(s["atk_explicit"]["GP_excl"]), _f(s["atk_explicit"]["GP_frame"])],
                            ["Explicit attacks in mixed documents", _f(m["explicit"]["B13s"]), _f(m["explicit"]["PCL"]), _f(m["explicit"]["GP_excl"]), "-"],
                            ["Ungrounded legitimate rules", _f(s["pooled_ungrounded"]["B13s"]), _f(s["pooled_ungrounded"]["PCL"]), _f(s["pooled_ungrounded"]["GP_excl"]), _f(s["pooled_ungrounded"]["GP_frame"])],
                            ["Grounded legitimate rules", _f(s["pooled_grounded"]["B13s"]), _f(s["pooled_grounded"]["PCL"]), _f(s["pooled_grounded"]["GP_excl"]), _f(s["pooled_grounded"]["GP_frame"])],
                            ["Benign memories in mixed documents", _f(m["benign_derived_memories"]["B13s"]), _f(m["benign_derived_memories"]["PCL"]), _f(m["benign_derived_memories"]["GP_excl"]), "-"],
                            ["Legitimate high-impact rules (not pooled)", _f(s["ben_highimpact"]["B13s"]), _f(s["ben_highimpact"]["PCL"]), _f(s["ben_highimpact"]["GP_excl"]), _f(s["ben_highimpact"]["GP_frame"])]]))
        b.append(("cap", "Table 24.2. Gap 1 on held-out SA-7 and MSD-7: exclusion (and GP's framing) per arm."))
        b.append(("fig", "W1"))
        b.append(("cap", "Gap 1: explicit-attack exclusion against legitimate-rule exclusion per arm (SA-7 eval); GP's framed share is a delay, not an exclusion."))
        H = cl["holm_primary_family"] if cl else {}
        beh = g3["behaviour"] if g3 else None
        b.append(("p", f"GP excludes more explicit attacks than B13 on stored text on single notes (Holm p = "
                       f"{H.get('G1-P1a GP vs B13s (single)', float('nan')):.1g}) and in mixed documents (Holm p = "
                       f"{H.get('G1-P1b GP vs B13s (MSD-7)', float('nan')):.1g}) while excluding fewer benign memories "
                       f"({s['benign_increase_points_GP_excl_minus_B13s']:+} and {m['benign_increase_points_GP_excl_minus_B13s']:+} points). "
                       f"Ungrounded legitimate rules excluded: {_f(s['pooled_ungrounded']['GP_excl'])} ({_p(s['pooled_ungrounded']['GP_excl'])}); "
                       f"on the stored-only subset {_stored_only_ung()}. Under every injected lineage corruption benign exclusion did not rise; "
                       f"wrong-link acceptance {_f(g1['flv']['wrong_link_acceptance'])}."
                       + (f" Behaviour on the trigger message: explicit unconfirmed activation fell from "
                          f"{_f(beh['atk_explicit']['stored']['unconfirmed_activation'])} to {_f(beh['atk_explicit']['GP']['unconfirmed_activation'])} "
                          f"(p = {beh['G1_P4_GP_vs_stored_explicit']['p_exact']:.2g}); legitimate untrusted-channel rules were acted on or "
                          f"offered {_f(beh['legit_untrusted_surfaced']['GP'])} under GP against {_f(beh['legit_untrusted_surfaced']['stored'])} "
                          f"undefended." if beh else "")))
        b.append(("p", f"Costs: {_f(s['pooled_ungrounded']['GP_excl_or_frame'])} ungrounded legitimate rules are excluded or framed "
                       f"(framing delays them behind a confirmation); legitimate high-impact rules are excluded "
                       f"{_f(s['ben_highimpact']['GP_excl'])}; implicit sleepers are not excluded by GP ({_f(s['atk_implicit']['GP_excl'])}) "
                       "but framed and left to the Gap-3 defences."))
    if g2:
        ins, fac, rec = g2["by_payload"]["instruction"], g2["by_payload"]["factual"], g2["recovery"]
        b.append(("h2", "24.3 Gap 2: no-decay containment with sentence-level fingerprints (HO10, held-out)"))
        b.append(("table", [["Arm", "Gen 1", "Gen 2", "Gen 3", "Gen 4", "Non-carrying withheld", "Gen-4 influence left"]] +
                  [[a] + [_f(ins[a]["withheld_carrying"][k]) for k in range(4)] + [_p(ins[a]["noncarrying_withheld_pooled"]),
                   _f(ins[a]["influence_remaining"][3])] for a in ("FG", "ND", "PRC", "RAR-S", "ND|RAR-S")]))
        b.append(("cap", f"Table 24.3. HO10 instruction payloads, {ins['n_flagged_roots']} flagged roots: payload-carrying descendants "
                         f"withheld per generation (undefended generation-4 influence {_f(ins['influence_undefended'][3])}). Unflagged "
                         "collateral 0 for every arm."))
        b.append(("fig", "W2"))
        b.append(("cap", "HO10 instruction-payload containment across consolidation generations."))
        bt = ins["owner_cluster_bootstrap_ND|RAR-S_g4"]
        b.append(("p", f"ND|RAR-S (the frozen guard without decay, or a sentence-level claim fingerprint) withholds "
                       f"{_f(ins['ND|RAR-S']['withheld_carrying'][3])} = {_p(ins['ND|RAR-S']['withheld_carrying'][3])} at generation 4 "
                       f"and meets every pre-registered criterion; the margin is two descendants and the owner-cluster interval is "
                       f"{100 * bt['ci95_owner_cluster'][0]:.1f}-{100 * bt['ci95_owner_cluster'][1]:.1f}%. ND alone reaches "
                       f"{_f(ins['ND']['withheld_carrying'][3])}, so removing decay carries most of the gain. PRC reaches "
                       f"{_f(ins['PRC']['withheld_carrying'][3])}. Factual payloads were under-powered "
                       f"({fac['ND|RAR-S']['withheld_carrying'][3]['n']} carrying descendants; ND|RAR-S "
                       f"{_f(fac['ND|RAR-S']['withheld_carrying'][3])}) and, read strictly, failed."))
        c2 = rec["C2_deleted_then_rewritten_SIMULATION"]
        b.append(("p", "Lineage recovery: with lineage deleted and the append-only log intact, recovery is exact "
                       f"({_f(rec['C1_deleted_log_intact']['recovery_correct_g4'])}, no false association). With the memory also "
                       f"rewritten (simulation), DCR-2 -- which compares only sentences not attributable to the owner's own memories "
                       f"-- withholds {_f(c2['withheld_carrying_g4(carry judged on rewritten text)'])} rewritten carriers against "
                       f"{_f(rec['A_lineage_present']['withheld_carrying_g4'])} with lineage present, at "
                       f"{_p(c2['false_association_owner_store'])} owner and {_p(c2['false_association_unflagged_benign_desc'])} "
                       "benign false association, but rarely names the exact source root "
                       f"({_f(c2['recovery_correct_g4'])}). A logged-rewrite condition on a hash-chained log recovers every root "
                       "(reported beside 2.6, never credited: lineage is then not lost)."))
    if g3:
        C, beh = g3["conditions"], g3["behaviour"]
        e = C["E_validated_lineage(PRIMARY)"]
        b.append(("h2", "24.4 Gap 3: fresh SA-7 test of the sleeper operating point (held-out)"))
        b.append(("table", [["Condition", "Implicit detected", "Ungrounded legitimate flagged", "Grounded flagged", "Within limits"]] +
                  [[k.split("(")[0].replace("_", " "), _f(C[k]["atk_implicit"]), _f(C[k]["ungrounded_pooled"]), _f(C[k]["grounded_pooled"]),
                    "yes" if C[k]["meets_G3P2"] else "no"]
                   for k in ("B_transformed(baseline)", "C&K_metadata+stored", "D_original_record(v6 frozen)", "E_validated_lineage(PRIMARY)",
                             "A_original_text", "S_SIMULATION_authenticated_principal")]))
        b.append(("cap", "Table 24.4. SA-7 eval: implicit-sleeper detection and legitimate-rule false positives per information "
                         "condition (E is the pre-registered operating point; S is a simulation)."))
        b.append(("fig", "W3"))
        b.append(("cap", "Gap 3: detection against ungrounded legitimate-rule false positives per condition on SA-7 eval."))
        b.append(("p", f"E fails again: it detects {_f(e['atk_implicit'])} implicit sleepers but flags {_f(e['ungrounded_pooled'])} "
                       f"({_p(e['ungrounded_pooled'])}) legitimate ungrounded rules, all from document or unrecorded sources (it "
                       "already exceeded the limit on development data, 11/96). Two conditions that were not the operating point "
                       f"meet the numeric limits on this set -- C AND K ({_f(C['C&K_metadata+stored']['atk_implicit'])}, "
                       f"{_f(C['C&K_metadata+stored']['ungrounded_pooled'])}) and the provenance-free baseline B "
                       f"({_f(C['B_transformed(baseline)']['atk_implicit'])}, {_f(C['B_transformed(baseline)']['ungrounded_pooled'])}) -- "
                       "and earn nothing under the pre-registration; E's lookup of the original record adds detection together with "
                       "the false positives."))
        b.append(("p", f"Behaviour: the two-stage frame halved implicit unconfirmed activation "
                       f"({_f(beh['atk_implicit']['stored']['unconfirmed_activation'])} to {_f(beh['atk_implicit']['TS']['unconfirmed_activation'])}) "
                       f"but not significantly (p = {beh['TS_vs_stored_implicit']['p_exact']:.2g}); the high-impact action gate had "
                       f"almost nothing to prevent ({_f(beh['atk_highimpact']['stored']['unconfirmed_activation'])} harmful actions "
                       f"undefended) and is under-powered; legitimate high-impact rules stayed usable "
                       f"({_f(beh['ben_highimpact_untrusted_surfaced']['HIG'])} under the gate). Counterfactual confirmation on E's flags "
                       f"confirmed {g3['F4_second_stage']['attack']['F4_confirmed']} attacks and {g3['F4_second_stage']['legit']['F4_confirmed']} "
                       "legitimate rules and cleared none. Document consistency judged every inserted rule out of place, attack or "
                       "legitimate"
                       + (f" ({_f(csd['dc_survival']['rule_record_inconsistent']['attack'])} and {_f(csd['dc_survival']['rule_record_inconsistent']['legit'])})"
                          if csd else "") +
                       "; beneficiary familiarity removed no false positive on development data. No provenance condition "
                       f"catches attacks relayed through the user ({_f(g3['URA_stratum']['E_validated_lineage(PRIMARY)'])} for E; "
                       f"content-only B {_f(g3['URA_stratum']['B_transformed(baseline)'])})."))
    b.append(("h2", "24.5 Engineering additions"))
    b.append(("p", "A tamper-evident ledger hash-chains every provenance record (optionally keyed) and detects edited, deleted, "
                   "reordered and truncated records; a rewrite log on the same chain gives exact recovery after a rewrite; "
                   "property and mutation tests check the v7 decision rules (13 deliberately broken copies, all caught). These are "
                   "verified by tests only and carry no held-out claim."))
    if cl:
        b.append(("h2", "24.6 Closure under the frozen rubric"))
        b.append(("table", [["Gap", "v6", "v7", "Capabilities that changed"]] +
                  [[g.split(": ")[1], f"{100 * v['before_v6']:.0f}%", f"{100 * v['after_v7']:.0f}%",
                    "; ".join(f"{c['name'].split(' ')[0]} {c['before']} -> {c['after']}" for c in v["capabilities"] if c["before"] != c["after"]) or "none"]
                   for g, v in cl["gaps"].items()]))
        b.append(("cap", "Table 24.6. Operational closure after v7 (no combined score). Details: docs/phase17/v7/RUBRIC_MAPPING.md."))
        b.append(("fig", "W4"))
        b.append(("cap", "Operational closure per gap after v5, v6 and v7."))
        b.append(("fig", "W5"))
        b.append(("cap", "The v7 defence architecture with each component's evaluated status (supersedes the v6 and "
                         "2026-10-14 architecture figures)."))
        b.append(("p", "Recorded interpretations: Gap 2's factual sub-test is read strictly (an under-powered failure lowers 2.3; the "
                       "lenient reading would give 75%); 2.2 passes by two descendants; 2.6 is relative to a weak lineage-present "
                       "matcher; Gap 3 stays capped because E fails the joint detection and benign limit."))
        b.append(("h2", "24.7 Limitations"))
        b.append(("p", "Gap 3 is unchanged: legitimate rules that arrive through documents or without a recorded source still look "
                       "like planted rules to every signal tested, and the 7B agent rarely acted on the sleepers in this set, which "
                       "left the behavioural tests with low base rates. SA-7 reuses the SA-6 owners and generator (items are new and "
                       "owner-disjoint between its own splits). Channel labels are application-recorded, not authenticated. Judges "
                       "are LLMs. The next pre-registered candidate for Gap 3 is C AND K, on a fresh set; for Gap 2, a powered factual "
                       "set; for all gaps, the authenticated-writer layer for Mem0."))
    return b


def write(H, P, TBL, CAP, FIGV):
    """FIGV(key, caption) places a v7 figure with a numbered caption (or nothing if the figure does not exist)."""
    bl = blocks()
    i = 0
    while i < len(bl):
        kind, x = bl[i]
        if kind == "fig":
            cap = bl[i + 1][1] if i + 1 < len(bl) and bl[i + 1][0] == "cap" else ""
            FIGV(x, cap)
            i += 2 if cap else 1
            continue
        if kind == "h":
            H(x, 1)
        elif kind == "h2":
            H(x, 2)
        elif kind == "p" and x:
            P(x)
        elif kind == "table":
            TBL(x)
        elif kind == "cap":
            CAP(x)
        i += 1
