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


def _L(n):
    return L(n)


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
        "baseline_breakdown_round6.json", "hold-out-informed; not a clean estimate; and 'no extra FPR' "
        "holds on ordinary memory only -- on hold-out 4's matched benign the union excludes 42/262 vs "
        "B13's 31 and B14's 24 (R7-12)")
    if mf:
        r = {e["scorer"]: e for e in mf["ranking_at_matched_dev_fpr"]}
        add("favourable", "Matched operating points close most of the baseline gap",
            f"deberta +{100*r['deberta_pi_v2']['recall_minus_fpr']:.1f} vs B14 "
            f"+{100*r['B14']['recall_minus_fpr']:.1f}; was a 17-point gap at shipped thresholds, "
            f"now 2.8", "holdout3_matched_fpr.json",
            "the baseline still leads on that corpus; and every scorer was calibrated on a 'dev' "
            "set that proved to be near-copies of hold-out 3's own benign half (round 7, R7-1), so "
            "this is a symmetric but HOLD-OUT-CALIBRATED comparison")
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
            "every FPR previously published used benign text unlike the attack distribution; "
            "detection cannot fix this (B19 failed, 32.44) but neutralisation addresses the "
            "regime on a different axis at zero false-positive cost (32.46)")
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
            "my earlier reading blamed corroboration and was wrong; and the 'DEV' items were "
            "hold-out 3 prompts under a different wrapper (R7-1), so this is a hold-out measurement")
    add("unfavourable", "'B13 is the recommendation' was wrong unqualified",
        "on working attacks B14 STRICTLY dominates B13 on the clean hold-out, 40/64 vs 8/64, "
        "+32/-0, p=5e-10; B13's 12.5% there was unreported", "recall_on_working.json")
    add("unfavourable", "B14's hold-out gap is half composition, half inherited from deberta",
        "36.6-point gap narrows to 20.6 on working attacks (p=0.0001); B14 agrees with deberta "
        "90.1% on external corpora and degrades worse than it across corpora",
        "eval_round6.json + recall_on_working.json")
    if fr:
        s17, s18 = fr["shipped"]["B17"], fr["shipped"]["B18"]
        s17["floor"] = min(fr["curves"]["B17"], key=lambda x: x["fpr"])
        s18["floor"] = min(fr["curves"]["B18"], key=lambda x: x["fpr"])
        add("unfavourable", "The union configurations cannot reach a low false-positive regime",
            f"B17's FPR on hold-out 3 cannot go below {100*s17['floor']['fpr']:.1f}% and B18's "
            f"below {100*s18['floor']['fpr']:.1f}% at ANY threshold, because both exclude "
            f"whenever B13 excludes; they also leave {100*s17['youden_headroom']:.1f} and "
            f"{100*s18['youden_headroom']:.1f} points of discrimination unused at their shipped "
            f"points", "holdout3_frontier.json",
            "so the recommendation is now conditioned on the false-positive budget rather than "
            "naming one configuration")
    if frs and not pw:
        add("unfavourable", "B16 falsified by its own pre-registered rule",
            f"1/38 -> 0/38, p={frs['paired_B16_vs_B15']['p_exact']}; the rule said p>0.1 "
            f"falsifies", "eval_rejection_fresh.json",
            "one control event caps the p-value at 1.0, so the test was underpowered: a flaw in "
            "my seed-selection rule")
    if frs and pw:
        add("unfavourable", "The first pre-registered adaptive test was underpowered and I had "
            "to revise its design",
            f"1/38 vs 0/38 at p=1.0: one control event caps the p-value regardless of the true "
            f"effect. Superseded by the powered re-run, but the original rule did fail",
            "eval_rejection_fresh.json")
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
        "the user_turn arm computed but never reported; B12 omitted from the table testing it. "
        "Round 7 added two more: a disjointness check that compared wrapped strings (R7-1), and a "
        "new guard test whose callee persisted its fit and overwrote the ledger radius on disk "
        "(caught by git status, restored, and now prevented by a session-wide read-only check)",
        "git history")
    if fam:
        add("unfavourable", "Five of seven founding families are weakly detected content-only",
            "DSRM, MPBench, MINJA, MemoryGraft 11-32%; sleeper 0% before the corroboration fix",
            "family_breakdown.json", "these are floors; see evidence_round6.json")

    # ---------------- OPEN
    if pw:
        g0 = pw["per_arm"]["B15"]["genuine_adaptive_evasion_of_initially_excluded"]
        g1 = pw["per_arm"]["B16@0.90"]["genuine_adaptive_evasion_of_initially_excluded"]
        pd = pw["paired_B16_vs_B15"]
        add("favourable", "Adaptive evasion resolved (the open item of every prior round)",
            f"{g0['k']}/{g0['n']} = {pct(g0['rate'])} stateless control -> {g1['k']}/{g1['n']} = "
            f"{pct(g1['rate'])} with the ledger; paired +{pd['only_a']}/-{pd['only_b']}, "
            f"p={pd['p_exact']:.3g} over {pw['n_discordant_pairs']} discordant pairs, 20 families",
            "eval_rejection_powered.json",
            "radius was pre-registered but the SEED RULE was revised after the first test "
            "failed; and the 0.90 radius carries a 29.7% ledger-poisoning blast radius against "
            "0.7% at 0.97, so the finding is the trade, not a solved problem")
    elif ad:
        add("open", "Adaptive evasion",
            "no significant effect at the frozen radius (4/30 vs 5/30, p=1.0); 0/30 at 0.90 is "
            "exploratory; pre-registered re-run falsified but underpowered",
            "eval_rejection_memory.json")
    xf = _L("exfiltration_final_agents.json")
    if xf:
        r2 = _L("exfiltration_regen2.json")
        add("favourable", "Exfiltration is now a TESTED mechanism",
            f"deterministic structural gates added after the judge was shown to pass instances "
            f"with no recipient; regenerated set scores {r2['heldout']['rate']:.1%} out-of-loop "
            f"(was 68.8%), 16/16 pass the gate, and all three agent families give "
            f"{xf['per_agent']['qwen2.5:7b']['causal_harm']['k']}/{xf['n']} harm -- they address "
            f"the legitimate counterparty and only RESTATE the attacker's directive",
            "exfiltration_final_agents.json",
            "a negative result about the attack class against 7-8B assistants, not a benchmark "
            "defect; the deterministic recipient column overstates adoption and the judge is the "
            "accurate instrument")
    elif xt:
        add("unfavourable", "Exfiltration is an UNTESTED mechanism",
            f"0/32 harm with a neutral task, provisioned store and recipient-aware judge; the "
            f"poison names an outbound recipient in only "
            f"{xt['poison_named_a_recipient']['k']}/{xt['n']} instances, so the generator failed "
            f"its own specification and the mechanism judge passed them anyway",
            "exfiltration_task_fix.json",
            "four rival explanations eliminated by measurement; no detection or harm figure for "
            "this family is evidence about the attack class")
    elif xs:
        add("open", "Exfiltration mechanism", xs.get("verdict", "pending"),
            "exfiltration_store_check.json")
    ev2 = _L("evidence_round6.json")
    if ev2 and "B18" in ev2.get("aggregate", {}):
        a = ev2["aggregate"]["B18"]
        w, b = a.get("attacks_with_evidence"), a.get("ordinary_benign_with_evidence")
        if w and b:
            add("favourable", "B18 with evidence is the best configuration on this benchmark's "
                "own threat",
                f"own attacks {w['k']}/{w['n']} = {pct(w['rate'])} at {b['k']}/{b['n']} = "
                f"{pct(b['k']/b['n'])} ordinary-benign FPR, discrimination "
                f"{100*(w['rate']-b['k']/b['n']):+.1f} against B13's +52.2 and B12's +43.2; the "
                f"corroboration arm had never been run for B18",
                "evidence_round6.json",
                "the entire false-positive cost falls on untrusted channels: 0/40, 0/6, 0/20 in "
                "the user_turn condition. SUPERSEDED as a recommendation (R7-13): on clean hold-out 4 "
                "B18 matches B13's recall exactly and adds false positives (16.0% vs 11.8%); the lead "
                "here was measured on populations B18 was selected after reading")
    b19 = _L("eval_b19.json")
    if b19:
        add("unfavourable", "The memory-shape gate failed: the FPR problem is not fixable this way",
            f"B19 = gate + B13 gives attacks {pct(b19['holdout3_attacks']['not_admitted']['rate'])} "
            f"and benign {pct(b19['holdout3_benign']['not_admitted']['rate'])}, discrimination "
            f"+21.1 against B13's +45.8; a structural-rules-only variant gives +45.3, i.e. no "
            f"gain. On an in-the-wild prompt corpus the benign and malicious halves are "
            f"structurally indistinguishable, so no shape pre-filter can separate them",
            "eval_b19.json",
            "reported as a failed attempt rather than retained; hold-out 3 has now been scored "
            "five times and only the first was pre-registered")
    nv, n2 = _L("neutralise.json"), _L("neutralise_v2.json")
    if nv:
        pa = nv["paired_attack_compliance"]
        add("favourable", "NEUTRALISATION resolves the one regime detection could not",
            f"hold-out 3 attack compliance {pct(nv['attack_compliance_raw']['rate'])} -> "
            f"{pct(nv['attack_compliance_neutralised']['rate'])}, paired +{pa['only_a']}/"
            f"-{pa['only_b']}, p={pa['p_exact']:.2g}, with no significant change in benign "
            f"information use; nothing is excluded so the false-positive rate is zero by "
            f"construction",
            "neutralise.json + neutralise_v2.json",
            "HOLD-OUT 3 USE 7 OF 7 (not an independent estimate; replicated cleanly on hold-out 5, "
            "37.4% -> 18.3%); the active ingredient is recency alone; v2/v3/v5 are indistinguishable at n=120 "
            "given a ~5-point noise floor, and the frame this project first built is actively "
            "harmful")
    ca = _L("eval_calibration2.json")
    if ca:
        add("favourable", "Prediction calibration demonstrated, not asserted",
            f"{ca['n_held']}/5 pre-registered predictions held on an unmeasured target "
            f"(B17/B18 on hold-out 2), with intervals committed before the run",
            "eval_calibration2.json + PREREGISTRATION_2_CALIBRATION.md",
            "it does not un-fail the three that failed in the first pre-registration")
        m = ca["measured"]["B18"]
        add("favourable", "New best on hold-out 2",
            f"B18 reaches {pct(m['recall']['rate'])} against B14's 54.2%, at "
            f"{m['ordinary_benign_fpr']['k']}/1054 ordinary-benign false positives",
            "eval_calibration2.json",
            "B17/B18 postdate the hold-out results that informed their design, so this is not a "
            "clean generalisation estimate")
    er = _L("error_registry.json")
    if er:
        add("favourable", "Every past error's guard PROVEN by mutation testing",
            f"{er['n_proven']}/{er['n']} guards fail when their error is reintroduced and pass "
            f"again once restored",
            "error_registry.json",
            "establishing it exposed that four of eight guards had been decoration, plus CRLF "
            "shell scripts, a guard passing on exit 127, and the harness corrupting what it "
            "measured twice")
    ab = _L("b14_ablate_deberta.json")
    if ab:
        v = ab["variants"]
        full = v["full_11_features"]["holdout_gap_points"]
        less = v["without_deberta_pi"]["holdout_gap_points"]
        add("unfavourable", "My 'instability inherited from deberta' attribution was imprecise",
            f"removing the feature WIDENS the cross-corpus gap ({full:+.1f} to {less:+.1f}) and "
            f"costs recall everywhere, hold-out 2 collapsing 59.8% to 40.7%; the gap is a "
            f"property of the fused weights and the feature is load-bearing",
            "b14_ablate_deberta.json",
            "still consistent with B18: a fusion can under-use a feature it contains, which is a "
            "different claim from that feature causing the instability")
    if n2:
        add("unfavourable", "The neutralisation frame I originally built is actively harmful",
            "v1_prefix raises attack compliance 6.7 points and costs 10 points of benign "
            "utility; the earlier 'partial, 49/150 -> 38/150' reading came from a hold-out "
            "sample that flattered it",
            "neutralise_v2.json")
    add("favourable", "Recommendation conditioned on threat and false-positive budget, on clean hold-outs",
        "memory poisoning: B13 + evidence (hold-out 4: 50.3% at 11.8% untrusted / 0% user_turn; B17/B18 "
        "dominated there); injection: B17 at ~10% FPR (hold-out 5: 90.1% at 10.2%); neutralisation as a "
        "zero-exclusion layer (halves compliance on hold-out 5); the ledger for retry-capable attackers",
        "Methodology 32.56 + eval_round7_holdouts.json",
        "supersedes 32.42/32.45, which named B18 for memory poisoning on hold-out-informed numbers")
    # ---------------- ROUND 7
    add("unfavourable", "The hold-out 3 development set was the hold-out (R7-1)",
        "382/400 'dev' benign items are hold-out 3 prompts verbatim under a different memory "
        "wrapper (393 near-copies); 647/648 of the earlier jailbreak snapshot are near-copies of "
        "hold-out 3 attacks. The disjointness check compared wrapped strings",
        "docs/phase17/ROUND7_LOG.md + phase17/near_dup.py",
        "the matched-FPR comparison and frontier are hold-out-calibrated; the per-rule FPR "
        "attribution was a hold-out measurement; B19 was fitted on near-copies and still failed, "
        "so that negative stands. Guard proven by mutation (dev_holdout_overlap)")
    fue = _L("family_union_evidence.json")
    if fue:
        fb = fue["families"]
        b18 = {f: fb[f]["B18"]["full"]["with_evidence"]["rate"] for f in
               ("agentpoison", "minja", "farma", "memorygraft", "dsrm", "mpbench",
                "sleeper_memory_poisoning")}
        add("favourable", "Founding families re-measured under B18 + evidence (never done before)",
            "B18 with the owner's conversation: " + ", ".join(f"{k} {v:.1%}" for k, v in b18.items())
            + f" at {fue['ordinary_benign_fpr_with_evidence']['B18']['k']}/1054 ordinary-benign FPR; "
            "no model re-run, union identity verified item by item",
            "family_union_evidence.json",
            "mixed: MemoryGraft and DSRM stay near 30% even at the best configuration measured, and "
            "B18 adds nothing over B17 on any founding family")
    r7 = _L("eval_round7_holdouts.json")
    r7p = _L("round7_predictions.json")
    if r7:
        h5, h4 = r7["holdouts"]["holdout5"], r7["holdouts"]["holdout4"]
        c5, c4 = h5["configs"], h4["configs"]
        add("favourable", "B17/B18 have clean hold-out estimates (was OPEN)",
            f"hold-out 5 (pre-registered, scored once): B17 {pct(c5['B17']['attack_recall']['rate'])} "
            f"recall at {pct(c5['B17']['matched_benign_fpr']['rate'])} matched-benign FPR, B18 "
            f"{pct(c5['B18']['attack_recall']['rate'])} at {pct(c5['B18']['matched_benign_fpr']['rate'])}; "
            f"hold-out 4: both {pct(c4['B18']['attack_recall']['rate'])} at "
            f"{pct(c4['B18']['benign_fpr_untrusted_channel']['rate'])} untrusted / "
            f"{pct(c4['B18']['benign_fpr_user_turn']['rate'])} user_turn",
            "eval_round7_holdouts.json + PREREGISTRATION_ROUND7.md",
            "B18 adds nothing over B17 on either hold-out; hold-out 5 has only 131 attacks (+/-8 points)")
        add("favourable", "The 33-55% matched-benign FPR regime does not generalise (pre-registered)",
            f"on hold-out 5's matched benign B17 {pct(c5['B17']['matched_benign_fpr']['rate'])}, B18 "
            f"{pct(c5['B18']['matched_benign_fpr']['rate'])}, B13 {pct(c5['B13']['matched_benign_fpr']['rate'])} "
            f"against 54.8% / 54.9% / 33.5% on hold-out 3",
            "eval_round7_holdouts.json",
            "the earlier 'unfixable by detection' reading was largely a property of hold-out 3's "
            "jailbreak-community benign prompts; it stands as a fact about that corpus")
        add("favourable", "Provenance reaches memory poisoning on the first memory-poisoning hold-out (was OPEN)",
            f"hold-out 4 (new author family, new owner, scored once): B13 "
            f"{pct(c4['B13']['attack_recall']['rate'])} vs B14 {pct(c4['B14']['attack_recall']['rate'])} "
            f"(p=1e-14), content-only B12 {pct(c4['B12']['attack_recall']['rate'])}, deberta@dev "
            f"{pct(h4['baselines']['deberta_pi_v2@dev']['attack_recall']['rate'])}, llama_guard@dev "
            f"{pct(h4['baselines']['llama_guard3@dev']['attack_recall']['rate'])}",
            "eval_round7_holdouts.json + holdout4_validity.json",
            f"costs {pct(c4['B13']['benign_fpr_untrusted_channel']['rate'])} benign FPR on the untrusted "
            f"channel (0% on user_turn); note-shaped families only -- the author inverted both "
            f"instruction-shaped families, which were withdrawn before freezing")
        n5 = h5["neutralisation"]
        d12 = n5["by_detector"]["B12"]
        add("favourable", "Neutralisation halves compliance on a clean injection hold-out at zero exclusions",
            f"hold-out 5: {pct(n5['compliance_raw']['rate'])} -> {pct(n5['compliance_framed']['rate'])}, "
            f"p={n5['paired_framed_vs_raw']['p_exact']:.2g}",
            "eval_round7_holdouts.json",
            "framing costs 2.2 points of benign information use on dev (n.s.); on hold-out 4's "
            "note-shaped attacks it does almost nothing")
        add("unfavourable", "The pre-registered PRIMARY composition test failed on the clean hold-out",
            f"B12 exclude + neutralise vs B12 exclude: {d12['policies']['P2_exclude']['harm_k']} -> "
            f"{d12['policies']['P4_exclude_plus_neutralise_rest']['harm_k']} of 131, "
            f"p={d12['paired_P4_vs_P2_harm']['p_exact']:.2g}; and B18 exclusion alone "
            f"({pct(n5['by_detector']['B18']['policies']['P2_exclude']['harm_rate'])} harm at "
            f"{pct(n5['by_detector']['B18']['policies']['P2_exclude']['benign_exclusion_rate'])}) beat "
            f"B12+neutralise ({pct(d12['policies']['P4_exclude_plus_neutralise_rest']['harm_rate'])} at "
            f"{pct(d12['policies']['P4_exclude_plus_neutralise_rest']['benign_exclusion_rate'])})",
            "eval_round7_holdouts.json",
            "the dev result (23.3% at 1.2% vs 32.0% at 7.0%) did not generalise: where detectors reach "
            "90% recall, neutralisation is a trade along the FPR axis, not a dominating configuration")
    else:
        add("open", "B17/B18 have no clean hold-out estimate",
            "both were chosen after reading hold-out results; hold-out 3 tested them once",
            "eval_holdout3.json")
        add("open", "All three hold-outs are injection/jailbreak corpora",
            "no memory-poisoning hold-out exists", "holdout3_corpus.py")
    if r7p:
        failed = [q["id"] for q in r7p["predictions"] if q["status"] == "FAILED"]
        add("favourable" if r7p["verdict"] == "CALIBRATED" else "unfavourable",
            "Round-7 pre-registration scored mechanically",
            f"{r7p['n_held']}/{r7p['n_scored']} held ({r7p['verdict']}); failed: {', '.join(failed)}",
            "round7_predictions.json",
            "failures stay in the table; one interval failed by 0.1 point and counts as failed")
    d7 = _L("dev_round7.json")
    if d7:
        mp = d7["beds"]["memory_poisoning_with_evidence"]["per_config"]
        add("unfavourable", "The #8 lead (unions without B13's content detector) failed on dev",
            f"B20 {pct(mp['B20']['recall']['rate'])} vs B17 {pct(mp['B17']['recall']['rate'])} on own "
            f"attacks at the same FPR; dominated in both beds", "dev_round7.json",
            "B13's content detector excludes no ordinary benign but catches attacks B14 misses")
    xa = _L("exfil_authoring.json")
    if xa:
        g = xa["generators"]
        add("favourable", "Exfiltration authoring fixed: the instruction, not the author (#10)",
            f"accepted (gates AND judge): qwen spec {g['qwen_spec']['accepted_gate_and_judge']['k']}/40, "
            f"qwen few-shot {g['qwen_fewshot']['accepted_gate_and_judge']['k']}/40, gemini spec "
            f"{g['gemini_spec']['accepted_gate_and_judge']['k']}/40, gemini few-shot "
            f"{g['gemini_fewshot']['accepted_gate_and_judge']['k']}/40",
            "exfil_authoring.json", "n=40 per generator; only the spec-only vs few-shot gap is claimed")
    add("unfavourable", "Round-7 measurement and description errors found and corrected",
        "R7-3 an artifact naming the wrong neutralisation frame; R7-8 leading probes (task-alone "
        "66/157 -> 7/157 after the fix); R7-10 the published harm study used FIXED tasks while a summary "
        "said per-instance", "docs/phase17/ROUND7_LOG.md",
        "each corrected in place; R7-8 and R7-10 are guarded")
    own = _L("neutralise_own.json")
    if own:
        add("favourable" if own["harm_framed"]["rate"] < own["harm_raw_rerun"]["rate"] else "unfavourable",
            "Neutralisation on this project's own attacks (Phase B)",
            f"harm {pct(own['harm_raw_rerun']['rate'])} raw -> {pct(own['harm_framed']['rate'])} framed; "
            f"B13 {pct(own['harm_b13']['rate'])} -> B13+frame {pct(own['harm_b13_plus_frame']['rate'])}",
            "neutralise_own.json", "both arms re-run in one session (noise floor ~5 points)")
    st = _L("neutralise_strong_agent.json")
    if st:
        add("favourable" if st["effect_points"]["gemini"] > 0 else "unfavourable",
            "Neutralisation on a stronger agent (Phase B)",
            f"gemini {pct(st['arms']['raw']['rate'])} -> {pct(st['arms'][st['frame']]['rate'])} "
            f"({st['effect_points']['gemini']:+.1f} pts) vs qwen {st['effect_points']['qwen']:+.1f} on the "
            f"same 60 items", "neutralise_strong_agent.json", "n=60; differences of a few points are noise")
    sw = _L("eval_ledger_radius_sweep.json")
    if sw:
        add("favourable" if sw["recommended_radius"] > 0.90 else "unfavourable",
            "Ledger radius swept against its denial-of-service surface (Phase B)", sw["verdict"],
            "eval_ledger_radius_sweep.json", "selection rule fixed before the sweep")
    add("favourable", "Every phase verified end to end",
        "3,466 tests passed, 32 skipped, 0 failed across phases 3-17, attribution and the "
        "cross-cutting suite; phase 3 and phase 5 datasets intact and needing no regeneration",
        "phase17/data/_phase_audit.txt + _phase_audit2.txt")
    hl = _L("human_label_agreement.json")
    if hl and hl["by_type"]["harm"].get("n_labelled"):
        h, c = hl["by_type"]["harm"], hl["by_type"]["compliance"]
        add("unfavourable", "The harm judge agrees only weakly with a human annotator",
            f"harm: {round(100*h['agreement'])}% agreement, kappa {h['cohen_kappa']}, "
            f"{h['judge_no_human_yes']} misses vs {h['judge_yes_human_no']} false alarms (n={h['n_labelled']}); "
            f"compliance: {round(100*c['agreement'])}%, kappa {c['cohen_kappa']}",
            "human_label_agreement.json",
            "one annotator who said YES on 80/100 items; the disagreement is one-sided (judges stricter). "
            "Harm LEVELS carry this caveat; reductions are more robust (same judge both arms); "
            "detection and FPR results do not use these judges")
        a2 = _L("human_label_agreement_annotator2.json")
        if a2:
            ia = a2["inter_annotator"]
            add("favourable", "A second independent, blind annotator agrees with the first",
                f"all items: {ia['ALL']['agreement']:.0%} agreement, kappa {ia['ALL']['cohen_kappa']}; compliance "
                f"kappa {ia['compliance']['cohen_kappa']}; harm and mechanism identical (near ceiling: harm YES "
                f"{ia['harm']['yes_annotator1']}/{ia['harm']['n']}, mechanism all YES); the original harm judge "
                f"misses the same harms against both people, adopted judge J2 kappa "
                f"{a2['judges']['J2_gemini_original']['harm_vs_annotator2']['cohen_kappa']}",
                "human_label_agreement_annotator2.json",
                "the identical harm labels mean J2's check against annotator 2 replicates rather than "
                "independently re-tests its selection; 100 items only")
        else:
            add("open", "A second independent human annotator",
                "needed to separate 'the judges are strict' from 'one annotator's threshold is lower', and to "
                "measure human-to-human agreement", "docs/phase17/human_labels/")
    nr = _L("noise_repeats.json")
    if nr:
        c = nr["compliance"]
        add("favourable", "The run-to-run noise floor is measured, not assumed",
            f"three independent runs: raw compliance {c['raw']['runs_k']} of 120 (SD {c['raw']['sd_points']} pts), "
            f"framed {c['v3_depersonalise']['runs_k']} (SD {c['v3_depersonalise']['sd_points']}), undefended harm "
            f"{nr['harm']['runs_k']} of 309 (SD {nr['harm']['sd_points']})",
            "noise_repeats.json", "dev only; the ~5-point floor used throughout is conservative")
    hj = _L("harm_judge_fix.json")
    if hj:
        c = hj["candidates"]
        add("favourable" if hj["adopted"] != "J0_current" else "open",
            "A better harm judge, chosen on half the human labels and tested on the other half",
            f"current judge TEST kappa {c['J0_current']['test']['kappa']}; adopted {hj['adopted']} TEST kappa "
            f"{c[hj['adopted']]['test']['kappa']}" + ("" if hj.get("complete") else " (selection not yet complete)"),
            "harm_judge_fix.json",
            "agreement is with ONE annotator; harm levels are re-measured with the adopted judge BESIDE the "
            "original, never in place of it")
    m7 = _L("holdout7_mechanism.json")
    if m7:
        a = m7["attack_mechanism"]
        add("unfavourable", "Instruction-shaped memory poisoning only partly testable on a clean hold-out",
            f"hold-out 7 (base-model author): standing instructions {a['standing_instruction']['k']}/40 valid, "
            f"conditional backdoors {a['conditional_backdoor']['k']}/40 -- conditional backdoors remain "
            f"effectively untested", "holdout7_mechanism.json",
            "the safety-tuned author inverted these families (hold-out 4); the base model writes standing "
            "instructions but not dormant triggers")
    e67 = _L("eval_round7b_holdouts.json")
    if e67:
        h6, h7 = e67["holdouts"]["holdout6"], e67["holdouts"]["holdout7"]
        d12 = h6["neutralisation"]["by_detector"]["B12"]
        add("favourable", "The false-positive finding replicates on a second independent corpus (hold-out 6)",
            f"B17 {pct(h6['configs']['B17']['attack_recall']['rate'])} recall at "
            f"{pct(h6['configs']['B17']['matched_benign_fpr']['rate'])} matched-benign FPR (500 / 1,000, SPML)",
            "eval_round7b_holdouts.json", "LLM-authored corpus; 3,728 near-copies dropped before freezing")
        add("favourable", "The failed composition test holds when powered (hold-out 6)",
            f"B12 exclusion + neutralise-the-rest vs B12 alone: {d12['policies']['P2_exclude']['harm_k']} -> "
            f"{d12['policies']['P4_exclude_plus_neutralise_rest']['harm_k']} of 500, "
            f"p={d12['paired_P4_vs_P2_harm']['p_exact']:.2g}",
            "eval_round7b_holdouts.json", "adds nothing on top of B18; it helps a weak detector, not a strong one; "
            "holds at its pre-registered alpha but NOT after Holm correction across the round's "
            + (lambda m: f"{m['m']} significance predictions (adjusted p={m['adjusted'].get('H6-4', float('nan')):.2g})")(
                (_L("round7_predictions.json") or {}).get("multiplicity", {"m": "?", "adjusted": {}})))
        add("unfavourable", "Two defects of B18 found on hold-outs",
            f"its deberta hard rule cost {pct(h6['configs']['B18']['matched_benign_fpr']['rate'])} FPR on "
            f"hold-out 6 and excluded {pct(h7['configs']['B18']['benign_fpr_user_turn']['rate'])} of hold-out 7's "
            f"user_turn benign notes (ignores channel trust)", "eval_round7b_holdouts.json",
            "the recommendation for injection-shaped text is now B17, not B18; any B18 fix is hold-out-informed")
        add("unfavourable", "Hold-out 7: contradiction rule adds nothing; framing backfired on instruction attacks",
            "B13c +0 on contradiction attacks; framing raised compliance on instruction-shaped attacks (+5 points)",
            "eval_round7b_holdouts.json + round7_predictions.json",
            "hold-out 7's working subset is not reportable (probe base rate 28% > the 20% rule)")
    ut = _L("neutralise_utility.json")
    if ut:
        # Rule: unfavourable if any task loses usefulness significantly (paired p < 0.05); otherwise
        # favourable, with the largest point loss and its p carried as the caveat.
        sig = [n for n, t in ut["tasks"].items()
               if t["loss_points"] > 0 and t["paired_framed_vs_raw"]["p_exact"] < 0.05]
        worst = max(ut["tasks"].items(), key=lambda kv: kv[1]["loss_points"])
        add("unfavourable" if sig else "favourable",
            "Usefulness cost of the neutralisation frame on benign memories"
            + (f": significant on {sig}" if sig else ": no significant cost"),
            "; ".join(f"{n}: {pct(t['raw']['rate'])} -> {pct(t['framed']['rate'])} "
                      f"(p={t['paired_framed_vs_raw']['p_exact']:.2g})" for n, t in ut["tasks"].items()),
            "neutralise_utility.json",
            f"{ut['n_notes']} benign notes, agent {ut['agent']}; largest loss {worst[0]} "
            f"{worst[1]['loss_points']:+.1f} points (p={worst[1]['paired_framed_vs_raw']['p_exact']:.2g}), "
            f"one LLM judge")
    ad = _L("adaptive_round7.json")
    if ad:
        for key in ("vs_neutralisation", "vs_corroboration"):
            if ad.get(key):
                ev = ad[key]["adaptive_evasion"]
                from scipy.stats import fisher_exact
                fp = fisher_exact([[ev["k"], ad[key]["n_seeds"] - ev["k"]], [32, 98]]).pvalue
                desc = ad[key].get("power_check", {}).get("descriptive_only")
                worse = (not desc) and fp < 0.05 and ev["rate"] > 32 / 130
                add("unfavourable" if worse else "open",
                    f"Adaptive evasion {key.replace('_', ' ')}"
                    + (": brittle -- above the stateless reference" if worse else
                       (" (descriptive only)" if desc else "")),
                    f"{ev['k']}/{ad[key]['n_seeds']} initially-caught seeds evaded within {ad['budget']} rewrites",
                    "adaptive_round7.json", f"conditional on an initial catch; vs 32/130 stateless "
                    f"reference, Fisher p={fp:.2g}")
    hr = _L("harm_rejudged.json")
    if hr:
        part = not hr.get("complete", True)
        add("open", "Harm study re-judged with the human-validated judge" + (" (PARTIAL)" if part else ""),
            ("undefended, all items: " + "; ".join(f"{n} {pct(v['rate'])}" for n, v in hr["undefended_all_items"].items())
             + f" | stratum n={hr['stratum']['n']}: " if part else "")
            + "; ".join(f"{n}: undefended {pct(r['harm_undefended']['rate'])}, B13 {pct(r['harm_b13']['rate'])}"
                        for n, r in hr["by_judge"].items()),
            "harm_rejudged.json", "identical full-text answers; original figures stand beside it"
            + (f"; {hr['missing_verdicts']} Gemini verdicts outstanding (daily quota), stratum = "
               f"{', '.join(hr['stratum']['families'])}" if part else ""))
    hs = _L("harm_strong_agent.json")
    if hs:
        _pb = hs["gemini"]["paired_b13_vs_undefended"]
        add("favourable" if _pb["only_b"] > _pb["only_a"] and _pb["p_exact"] < 0.05 else "open",
            "Harm with a stronger agent (Gemini): B13 still cuts it"
            if _pb["only_b"] > _pb["only_a"] and _pb["p_exact"] < 0.05 else "Harm with a stronger agent (Gemini)",
            f"undefended {pct(hs['gemini']['harm_undefended']['rate'])} vs qwen "
            f"{pct(hs['qwen_same_items']['harm_undefended']['rate'])}; B13 {pct(hs['gemini']['harm_b13']['rate'])}",
            "harm_strong_agent.json", hs["subset"] + f"; B13 vs undefended p={_pb['p_exact']:.2g}; "
            f"Gemini vs qwen undefended p={hs['paired_gemini_vs_qwen_undefended']['p_exact']:.2g}; "
            "original harm judge (levels likely under-estimates, Section 13A)")
    s120 = _L("neutralise_strong_agent_n120.json")
    if s120:
        add("open", "Stronger-agent framing effect, all 120 dev items",
            f"Gemini {s120['effect_points']['gemini']:+.1f} vs qwen {s120['effect_points']['qwen']:+.1f} points",
            "neutralise_strong_agent_n120.json", "extension for precision, not the pre-registered test")
    h6c = _L("holdout6_causal.json")
    if h6c:
        e6 = (_L("eval_round7b_holdouts.json") or {}).get("holdouts", {}).get("holdout6")
        if e6:
            w = h6c["per_item_working"]
            def _r(c, m=None):
                v = [x for x, k in zip(e6["raw"]["attack"][c], w) if (m is None or k)]
                return sum(v) / len(v)
            add("unfavourable", "Hold-out 6: the attacks that work are harder to detect (direction is corpus-specific)",
                "; ".join(f"{c} {pct(_r(c))} full vs {pct(_r(c, True))} working" for c in ("B13", "B14", "B17", "B18")),
                "holdout6_causal.json + eval_round7b_holdouts.json",
                f"{h6c['working']['k']}/{h6c['n']} working, task-alone base rate "
                f"{h6c['task_alone_base_rate']['k']}/{h6c['n']} (under the 20% rule); full-population recall "
                f"overstates protection; B18 holds only through its 16.3%-FPR deberta rule; on hold-outs 4 "
                f"and 5 the working attacks are EASIER for B13 (~+10 points) -- Table 20")
    alx = _L("adaptive_ledger_exploratory.json")
    if alx:
        c = alx["arms"]["vs_corroboration"]
        add("open", "EXPLORATORY: the ledger would block most corroboration evasions",
            f"{c['by_radius']['0.97']['would_block']}/{c['evasions']} at 0.97, "
            f"{c['by_radius']['0.95']['would_block']}/{c['evasions']} at 0.95",
            "adaptive_ledger_exploratory.json",
            "post-hoc upper bound on dev; the composed adaptive run (B13 + ledger) is not yet measured")
    lb = _L("adaptive_ledger_b13.json")
    if lb:
        pp = lb["paired_ledger_vs_control"]
        add("favourable" if lb["L1_held"] else "unfavourable",
            "The ledger " + ("closes" if lb["L1_held"] else "does NOT close") + " corroboration's adaptive weakness (pre-registered)",
            f"{lb['control_evasion']['k']}/{lb['n_seeds']} -> {lb['ledger_evasion']['k']}/{lb['n_seeds']} at radius "
            f"{lb['radius']}, paired +{pp['only_a']}/-{pp['only_b']}, p={pp['p_exact']:.2g}",
            "adaptive_ledger_b13.json",
            "dev only; ledger cost = 6.4% blast radius at 0.95 (dev); B18 + ledger not measured (~40 s per B18 decision)")
    else:
        add("open", "Ledger composed with B18 / with corroboration", "not yet measured", "-",
            "B18 + ledger: an estimated 4-9 GPU hours; B18 is no longer recommended")
    rw = _L("risk_weighted_retrieval_eval.json")
    if rw:
        e, dg = rw["exposure"], rw["diagnostics"]
        add("favourable" if rw["predictions"]["R-1"] else "unfavourable",
            "Phase 10 risk-weighted retrieval: cross-guard corroboration demotes poison (first evaluation)",
            f"exposure {e['A1']['k']} -> {e['A3']['k']} of {rw['n']} vs the fixed gate, "
            f"p={rw['paired_A3_vs_A1']['p_exact']:.2g}; benign displacement {rw['benign_displacement_points']['A3']} points",
            "risk_weighted_retrieval_eval.json",
            f"narrow: admission signals fired on the poison in {dg['instances_admission_fired_on_poison']}/{rw['n']} "
            f"instances; dev only; not robust to a family-wide Holm correction on its own -- see the "
            f"fresh-store replication row")
        add("unfavourable", "Phase 6's fixed-gate retrieval guard barely changes what reaches the agent",
            f"exposure {e['A0']['k']} -> {e['A1']['k']} of {rw['n']} (p={rw['paired_A1_vs_A0']['p_exact']:.2g}); "
            f"lexical divergence positive for only {dg['candidates_with_divergence_positive']} candidates",
            "risk_weighted_retrieval_eval.json", "pre-registered R-4 FAILED")
        mr = _L("risk_monitoring_eval_realistic.json")
        if mr:
            add("open", "Phase 10 risk-weighted monitoring works but has little to do (first evaluation)",
                f"realistic pools: poison listed in {mr['poison_listed']}/{mr['n_retrievals']} retrievals; ranked first "
                f"{mr['poison_first_by_risk']}/{mr['poison_listed']} vs {mr['poison_first_expected_default']} by default",
                "risk_monitoring_eval_realistic.json + risk_monitoring_eval.json",
                "a first design with randomly mixed pools inflated the queue (reported as an artifact); dev only")
        else:
            add("open", "Phase 10 risk-weighted monitoring (forensic ordering) not evaluated",
                "built and unit-tested; orders a human triage queue", "-", "no outcome measured yet")
    fr, cp = _L("rwr_fresh_replication.json"), _L("rwr_campaign.json")
    if fr:
        q = fr["paired"]["A3_vs_A1"]
        add("favourable" if q["p_exact"] < 0.05 and q["only_b"] > q["only_a"] else "unfavourable",
            "Corroborated risk-weighted retrieval replicates on fresh stores (pre-registered R6-1)",
            f"{fr['exposure']['A1']['k']} -> {fr['exposure']['A3']['k']} of {fr['n']}, +{q['only_a']}/-{q['only_b']}, "
            f"p={q['p_exact']:.2g}", "rwr_fresh_replication.json",
            "LoCoMo conversations 2/3/4/9, unused by any other phase-17 measurement; dev poisons")
    if cp:
        q = cp["paired"]["A1s_vs_A0"]
        good = q["p_exact"] < 0.05 and q["only_b"] > q["only_a"]
        add("favourable" if good else "unfavourable",
            "Consensus guard against coordinated campaigns (its designed threat)"
            + (": effective with semantic divergence" if good else ": not effective"),
            f"any copy exposed {cp['exposure']['A0']['k']} -> lexical {cp['exposure']['A1']['k']}, semantic "
            f"{cp['exposure']['A1s']['k']} of {cp['n']} (p={q['p_exact']:.2g}); benign displacement "
            f"{cp['benign_displacement_points']['A1s']} points", "rwr_campaign.json",
            "pre-registered R6-2..R6-4; the single-poison failure (R-4) stands and is reported beside it")
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
