"""Results Analysis section 23 (Defence v6, 2026-10-14/15), generated from the committed v6 artifacts. Called by
build_results_analysis_docx.py and update_methodology_v6.py with their own writer helpers. A sub-section whose
artifact does not exist yet is written as 'in progress' rather than with assumed values."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "phase17" / "data" / "defence_v6"


def _L(n):
    p = DATA / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _f(x):
    return f"{x['k']}/{x['n']}"


def _p(x):
    return f"{100 * x['k'] / x['n']:.1f}%" if x and x.get("n") else "n/a"


def blocks():
    """Ordered ('h'|'h2'|'p'|'table'|'fig'|'cap', payload) list shared by both documents."""
    g1, g2, w, fpb, g3, it, cl = (_L("g1_eval.json"), _L("g2_eval.json"), _L("g2_wtp_check.json"), _L("fpb_eval.json"),
                                  _L("g3_eval.json"), _L("integration_eval.json"), _L("closure_v6.json"))
    fsel, fselb, pw, top = _L("fpb_selection.json"), _L("fpb_selection_B.json"), _L("power_analysis.json"), _L("ho9_topup.json")
    clp, g3s = _L("clp_selection.json"), _L("g3_selection.json")
    b = []
    b.append(("h", "23. Defence Programme v6 (2026-10-14/15): Root-Cause Fixes"))
    b.append(("p", "Pre-registered in docs/phase17/PREREGISTRATION_DEFENCE_V6_2026-10-14.md (with addendum A) before any v6 "
                   "corpus existed. v6 targets the root causes left by v2-v5 -- authorship absent from stored text, Mem0's "
                   "rewriting of conditional rules into preference facts, lineage lost after writing, and under-powered "
                   "generation-4 tests -- and builds only new data, because every earlier evaluation set had been used."))
    b.append(("h2", "23.1 Design, new data and integrity record"))
    rows = [["Set", "Construction", "Size", "Use"],
            ["SA-6", "Gemini, SA-3 template; 6 kinds (implicit/explicit sleepers; ungrounded, grounded, future-plan and "
                     "unusual legitimate rules); channels assigned deterministically (user/document/missing)",
             "480 notes; dev owners 0,2,4,6 / eval 1,3,5,7,8,9", "Gaps 1 and 3; frozen 857bf53e"],
            ["MSD", "1 attack note + 2 legitimate notes per document (seeded)", "200 documents", "Claim-level provenance"],
            ["HO9", "HO7's generator (mistral:7b-text), owners 2,3,5,9", "460 instruction (265 flagged), 73 factual "
             "(31 flagged), 160 benign", "Gap 2, powered; frozen e38a4f80"],
            ["FPB", "8 controlled transformations per root (Gemini)", "dev 80 / eval 140 roots", "Claim fingerprints"]]
    b.append(("table", rows))
    b.append(("cap", "Table 23.1. New v6 data; nothing used earlier was re-used for confirmation."))
    if pw:
        b.append(("p", f"Power. The generation-4 containment test was sized by simulation from the spent HO7/HO8 rates: "
                       f"{pw['chosen_n_flagged_instruction_roots']} flagged instruction roots give power "
                       f"{pw['power_by_n_flagged_roots']['containment_pessimistic (HO7 survival 8/55, d=0.5, w=0.85)']['250']:.2f} "
                       "under the most pessimistic survival; 265 were obtained."))
    b.append(("p", "Deviations and defects (all recorded before the affected acceptance was assessed; defective outputs kept "
                   "as *_DEFECTIVE_*): (i) the HO9 author model was missing and was re-installed (same tag); (ii) the factual "
                   "top-up was aborted for compute, leaving factual payloads an under-powered secondary subset; (iii) the "
                   "pre-registered fingerprint failed its dev constraints and an entailment-led variant was pre-registered as "
                   "addendum A from dev evidence only; (iv) two lineage-validation defects (a channel-conflict exemption and "
                   "claim-level inheritance reading the wrong event) were fixed before any Gap-1 outcome; (v) a claim-linking "
                   "defect (claims pooled across events) was found in the first Gap-1 evaluation and corrected to the "
                   "pre-registered per-event rule; (vi) condition B's equality with A had been asserted by a placeholder and "
                   "was recomputed (296/296). Shared task and judge caches changed by additions only."))

    b.append(("h2", "23.2 Provenance through a real memory system"))
    if g1:
        pv, fu = g1["provenance"], g1["forced_update"]
        b.append(("p", f"Mem0 2.0.19's add(infer=True) only adds memories: across 680 ingestions there were "
                       f"{pv['natural_update_events']} natural UPDATE events, so laundering through extraction cannot occur in "
                       f"this version. Every derived memory carried its recorded channel natively and in the ledger "
                       f"({pv['ledger_channel_correct']}/{pv['derived_memories']}). A forced UPDATE through the public API "
                       f"relabelled the attack memory to 'user' in Mem0's own metadata in {fu['native_relabelled_to_user']}/{fu['n']} "
                       f"cases, while the append-only ledger kept the document source in {fu['ledger_still_untrusted']}/{fu['n']}; "
                       f"Mem0's native history recorded no writer on any row ({fu['native_history_rows_with_role_or_actor']}/{fu['n']}). "
                       "The ledger's labels are application-recorded, not authenticated."))
        b.append(("fig", "V1"))
        b.append(("cap", "Provenance through Mem0: native metadata against the application-level ledger."))

    b.append(("h2", "23.3 Claim-level provenance and fail-safe lineage (Gap 1)"))
    if g1 and clp:
        s, m, fl = g1["single_notes"], g1["msd"], g1["flv"]
        rows = [["Set (SA-6 eval)", "B13 on stored", "PAB13", "PCL (claim-level)", "Item-level"],
                ["Explicit attacks, single notes", _f(s["atk_explicit"]["B13s"]), _f(s["atk_explicit"]["PAB13"]),
                 _f(s["atk_explicit"]["PCL"]), _f(s["atk_explicit"]["ITEM"])],
                ["Explicit attacks, mixed-source documents", _f(m["explicit"]["B13s"]), _f(m["explicit"]["PAB13"]),
                 _f(m["explicit"]["PCL"]), _f(m["explicit"]["ITEM"])],
                ["Implicit attacks, single notes", _f(s["atk_implicit"]["B13s"]), _f(s["atk_implicit"]["PAB13"]),
                 _f(s["atk_implicit"]["PCL"]), _f(s["atk_implicit"]["ITEM"])],
                ["Ungrounded legitimate rules (pooled)", _f(s["pooled_ungrounded"]["B13s"]), _f(s["pooled_ungrounded"]["PAB13"]),
                 _f(s["pooled_ungrounded"]["PCL"]), _f(s["pooled_ungrounded"]["ITEM"])],
                ["Grounded legitimate rules", _f(s["pooled_grounded"]["B13s"]), _f(s["pooled_grounded"]["PAB13"]),
                 _f(s["pooled_grounded"]["PCL"]), _f(s["pooled_grounded"]["ITEM"])],
                ["Benign memories in mixed documents", _f(m["benign_derived_memories"]["B13s"]),
                 _f(m["benign_derived_memories"]["PAB13"]), _f(m["benign_derived_memories"]["PCL"]),
                 _f(m["benign_derived_memories"]["ITEM"])]]
        b.append(("table", rows))
        b.append(("cap", "Table 23.2. Items (or memories) excluded under each Gap-1 policy (SA-6 eval through Mem0)."))
        p1a, p1b = s["P1a_explicit_PCL_vs_B13s"], m["P1b_explicit_PCL_vs_B13s"]
        b.append(("p", f"Claim-level inheritance (link threshold from v3, margin delta = {clp['chosen']['delta']} selected on dev "
                       f"with {clp['chosen']['mislinked']}/{clp['chosen']['validated']} mis-links) recovers explicit attacks "
                       f"hidden by Mem0's rewriting: +{p1a['only_a']}/-{p1a['only_b']} on single notes and +{p1b['only_a']}/"
                       f"-{p1b['only_b']} on mixed-source documents (both p = {p1a['p_exact']:.1e}). It costs benign memories: "
                       f"+{m['benign_increase_points_PCL_minus_B13s']} points on mixed-document benign memories (limit 3) and more "
                       "exclusions of unusual-but-harmless rules, and it did not preserve benign memories better than item-level "
                       "inheritance. Provenance-aware corroboration (PAB13: corroborate only memories not sourced solely from "
                       f"user turns) halves ungrounded false exclusions ({_f(s['pooled_ungrounded']['B13s'])} -> "
                       f"{_f(s['pooled_ungrounded']['PAB13'])}; user channel {_f(s['ben_unground']['by_channel']['user']['B13s'])} -> "
                       f"{_f(s['ben_unground']['by_channel']['user']['PCL'])}) without changing detection, but remains above 10%."))
        rows = [["Corruption", "Benign change, with FLV (points)", "Benign change, naive", "Implicit kept (FLV / naive)"]]
        for k in ("wrong", "duplicate", "conflicting", "missing_parent", "digest_mismatch"):
            a, n = fl[f"{k}|FLV"], fl[f"{k}|naive"]
            rows.append([k.replace("_", " "), f"{a['benign_increase_points']:+.1f}", f"{n['benign_increase_points']:+.1f}",
                         f"{_f(a['implicit_PCL'])} / {_f(n['implicit_PCL'])}"])
        b.append(("table", rows))
        b.append(("cap", f"Table 23.3. Fail-safe lineage validation under injected corruptions. Wrong-link acceptance "
                         f"{_f(fl['wrong_link_acceptance'])}; correct-link acceptance {_f(fl['correct_link_acceptance'])}."))
        b.append(("fig", "V5"))
        b.append(("cap", "Gap 1: claim-level provenance against B13 on explicit attacks, and the benign cost."))

    b.append(("h2", "23.4 Claim fingerprints"))
    if fpb and fsel and fselb:
        rows = [["Matcher (FPB eval, 140 roots)", "Recall: payload-carrying", "False match: benign same-subject",
                 "Match: negation / action change"]]
        for a, lab in (("digest_only", "Digest only"), ("sem_only(0.5)", "Similarity only"), ("nli_only(0.00474)", "NLI only"),
                       ("HFP", "HFP (pre-registered; dev selection failing)"), ("HFP-B", "HFP-B (addendum A)")):
            r = fpb["arms"][a]["all"]
            rows.append([lab, _p(r["carry_recall"]), _p(r["benign_overlap"]), _p(r["neg_action_match"])])
        b.append(("table", rows))
        b.append(("cap", "Table 23.4. Claim fingerprints on held-out transformations."))
        b.append(("p", "A similarity branch cannot separate a descendant that carries the planted claim from a benign memory about "
                       "the same person, topic and named entity; entailment in both directions can (descendant entails root for "
                       "paraphrase and merge; root entails descendant for a partial claim). HFP-B was selected on dev only and "
                       "held on new roots."))
        b.append(("fig", "V2"))
        b.append(("cap", "Claim fingerprints on held-out FPB."))

    b.append(("h2", "23.5 Multi-generation containment on a powered held-out set (Gap 2)"))
    if g2:
        ins = g2["by_payload"]["instruction"]
        rows = [["Arm", "Gen 1", "Gen 2", "Gen 3", "Gen 4", "Non-carrying withheld", "Unflagged collateral (gen 4)"]]
        for a in ("FG", "ND", "RCL", "CTC", "PRC", "RAR", "RAR-B"):
            x = ins[a]
            rows.append([a] + [_f(v) for v in x["withheld_carrying"]] + [_f(x["noncarrying_withheld_pooled"]),
                                                                        _f(x["collateral_unflagged"][3])])
        b.append(("table", rows))
        p = ins["paired_gen4_PRC_vs_FG"]
        inf = ins["paired_gen4_influence_PRC_vs_A0"]
        b.append(("cap", "Table 23.5. HO9 instruction payloads: payload-carrying descendants withheld (265 flagged roots)."))
        b.append(("p", f"On a fresh set sized for power, payload-routed containment (PRC, frozen since v4) withheld "
                       f"{_f(ins['PRC']['withheld_carrying'][3])} payload-carrying generation-4 descendants against "
                       f"{_f(ins['FG']['withheld_carrying'][3])} for the frozen guard (+{p['only_a']}/-{p['only_b']}, p = "
                       f"{g2['holm_C2_instruction']['PRC']:.1e} after Holm) and reduced generation-4 behavioural influence "
                       f"({inf['detected_b']} -> {inf['detected_a']}, p = {inf['p_exact']:.3f}). It missed the pre-registered "
                       f"60% bar by one root ({_p(ins['PRC']['withheld_carrying'][3])}) and withheld "
                       f"{_p(ins['PRC']['noncarrying_withheld_pooled'])} of non-carrying descendants (limit 25%). Removing the "
                       f"guard's per-hop decay alone (ND) raised generation-4 containment from {_f(ins['FG']['withheld_carrying'][3])} "
                       f"to {_f(ins['ND']['withheld_carrying'][3])}. The root-anchored fingerprint rules failed "
                       f"(RAR-B {_f(ins['RAR-B']['withheld_carrying'][3])}): a 2-3 sentence consolidation of the payload with four "
                       "other memories neither entails nor is entailed by the root, a case the single-step benchmark did not "
                       "represent."))
        b.append(("fig", "V3"))
        b.append(("cap", "Containment across generations on HO9 instruction payloads."))

    b.append(("h2", "23.6 Lineage recovery after metadata loss"))
    if g2 and w:
        r = g2["recovery_HFP-B"]
        c1, c2, c3 = r["C1_deleted_log_intact"], r["C2_deleted_then_rewritten_SIMULATION"], r["C3_total_loss_reference"]
        rows = [["Condition", "Root recovered", "Owner memories falsely associated", "Unflagged descendants falsely associated"],
                ["A lineage present", "n/a", "n/a", "n/a"],
                ["B never persisted (write-time taint)", f"equal to A: {w['item_for_item_equal_to_A']}", "n/a", "n/a"],
                ["C1 deleted, append-only log intact", _f(c1["recovery_correct_g4"]), _f(c1["false_association_owner_store"]),
                 _f(c1["false_association_unflagged_benign_desc"])],
                ["C2 deleted then rewritten (simulation)", _f(c2["recovery_correct_g4"]), _f(c2["false_association_owner_store"]),
                 _f(c2["false_association_unflagged_benign_desc"])],
                ["C3 total loss (reference)", _f(c3["recovery_correct_g4"]), f"{_f(c3['collateral_owner_store'])} withheld",
                 f"{_f(c3['collateral_unflagged_benign_desc'])} withheld"]]
        b.append(("table", rows))
        b.append(("cap", "Table 23.6. Lineage recovery on HO9 (296 flagged attack chains); conditions are never pooled."))
        b.append(("p", "Lineage deleted after writing is recovered exactly from an append-only log keyed by content digest, with "
                       "no false associations, and can feed any containment rule. When the memory is also rewritten after "
                       "deletion, reconciliation still finds the right root but attaches most of the owner's own memories to "
                       "tainted roots, because consolidated summaries contain the owner's text; recovery after a rewrite needs "
                       "the rewrite itself to be logged."))
        b.append(("fig", "V4"))
        b.append(("cap", "Lineage recovery conditions."))

    b.append(("h2", "23.7 Implicit sleepers: the information boundary and a two-stage defence (Gap 3)"))
    if g3s:
        b.append(("p", f"Selection on SA-6 dev: no content detector on raw text met the limits alone (best {g3s['K']}); the "
                       f"deployable operating point frozen on dev is {g3s['operating_point']} (untrusted channel AND the detector "
                       "on the preserved original record)."))
    if g3:
        c = g3["conditions"]
        rows = [["Condition", "Implicit detected", "Explicit detected", "Ungrounded legit flagged", "Grounded legit flagged"]]
        for k, v in c.items():
            rows.append([k.replace("_", " "), _f(v["implicit"]), _f(v["explicit"]), _f(v["ungrounded_pooled"]), _f(v["grounded_pooled"])])
        b.append(("table", rows))
        b.append(("cap", "Table 23.7. The same SA-6 eval items under each information condition."))
        op = g3["P2_operating_point"]
        bh = g3["behaviour"]
        pa = bh["P1_acceptance"]
        t = bh["P1_TS_vs_stored_implicit"]
        b.append(("p", f"At the frozen operating point the held-out implicit detection is {_f(op['implicit_detection'])} with "
                       f"{_f(op['ungrounded_pooled'])} ungrounded and {_f(op['grounded_pooled'])} grounded legitimate rules "
                       f"flagged (pooled over the pre-registered channel mix). The two-stage defence changed implicit "
                       f"unconfirmed activation from {_f(bh['atk_implicit']['stored']['unconfirmed_activation'])} to "
                       f"{_f(bh['atk_implicit']['TS']['unconfirmed_activation'])} (+{t['only_a']}/-{t['only_b']}, p = "
                       f"{t['p_exact']:.3g}); pre-registered acceptance: {'accepted' if pa['accepted'] else 'not accepted'}."))
        b.append(("fig", "V6"))
        b.append(("cap", "Information boundary: detection and false positives per information condition."))
        b.append(("fig", "V7"))
        b.append(("cap", "Two-stage sleeper defence on Mem0-stored memories."))
    else:
        b.append(("p", "In progress: the held-out sleeper behaviour runs (two-stage defence, counterfactual activation) were "
                       "still running when this section was generated; no Gap-3 held-out result is stated here."))

    b.append(("h2", "23.8 Integration, ablation and closure"))
    if it:
        a = it["arms"]
        rows = [["Arm", "Implicit unconfirmed", "Explicit unconfirmed", "Ungrounded legit excluded", "Legit availability"]]
        for k in a:
            rows.append([k, _f(a[k]["atk_implicit"]["unconfirmed_activation"]), _f(a[k]["atk_explicit"]["unconfirmed_activation"]),
                         _f(a[k]["ungrounded_legit"]["excluded"]), _f(a[k]["memory_availability_legit"])])
        b.append(("table", rows))
        b.append(("cap", "Table 23.8. Integrated arms and ablations on SA-6 eval (behaviour on the trigger message)."))
    else:
        b.append(("p", "In progress: integration and ablation depend on the Gap-3 behaviour runs."))
    if cl:
        rows = [["Gap", "Capability", "Before", "After v6", "Evidence"]]
        for g, v in cl["gaps"].items():
            for cap in v["capabilities"]:
                rows.append([g, cap["name"], f"{cap['before']:.2f}", f"{cap['after']:.2f}", cap["evidence"]])
            rows.append([g, "Gap score (critical caps applied)", f"{v['before'] * 100:.0f}%", f"{v['after'] * 100:.0f}%", ""])
        b.append(("table", rows))
        b.append(("cap", "Table 23.9. Operational closure under the frozen rubric (no combined score)."))
        b.append(("fig", "V8"))
        b.append(("cap", "Closure before and after v6."))
    else:
        b.append(("p", "In progress: closure is scored after the Gap-3 results under the frozen rubric; until then the v5 "
                       "scores stand (Gap 1 59%, Gap 2 65%, Gap 3 29%)."))
    b.append(("fig", "V9"))
    b.append(("cap", "The v6 defence architecture with each component's evaluated status."))
    return b


def write(H, P, TBL, CAP, FIGV):
    """FIGV(key, caption) places a v6 figure with a numbered caption (or nothing if the figure does not exist)."""
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
        elif kind == "p":
            P(x)
        elif kind == "table":
            TBL(x)
        elif kind == "cap":
            CAP(x)
        i += 1
