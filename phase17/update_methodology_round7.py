# -*- coding: utf-8 -*-
"""Round 7 methodology update: corrections IN PLACE, then the round-7 sections.

WHY IN PLACE. Round 6 corrected several claims by writing new subsections (32.34, 32.39, 32.43,
32.47) and left the corrected sentences standing, unqualified, where a reader meets them first --
the overall conclusion (Section 33) still declared multi-hop outside the benchmark and adaptive
evasion open. Section 32.0 says "where a later subsection corrects an earlier one, both remain";
that is right for an audit trail only if the earlier one SAYS it was corrected. Each in-place edit
below appends a bracketed note to the original sentence rather than deleting it, so the history is
preserved and the reader is not misled.

IDEMPOTENT. Every edit carries a marker and is skipped if already applied, and every new section is
skipped if its heading exists, so the script can be re-run as round-7 results land. The guard
`test_no_superseded_claim_stands_unqualified[methodology_docx]` fails if any superseded claim is
left without its qualifier.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import docx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PATH = "Methodology Draft.docx"
DATA = Path("phase17/data")


def L(n):
    p = DATA / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


doc = docx.Document(PATH)
paras = doc.paragraphs
BODY = paras[4].style
applied, skipped = [], []


def find(startswith=None, contains=None):
    for p in doc.paragraphs:
        if startswith and p.text.startswith(startswith):
            return p
        if contains and contains in p.text:
            return p
    return None


def append_note(key, note, startswith=None, contains=None):
    """Append a bracketed note to an existing paragraph, once."""
    p = find(startswith, contains)
    if p is None:
        raise SystemExit(f"anchor not found for {key}: {startswith or contains!r}")
    if note in p.text:
        skipped.append(key)
        return
    p.add_run(" " + note)
    applied.append(key)


def replace_in(key, old, new, contains):
    if find(contains=new[:60]) is not None:          # already applied on an earlier run
        skipped.append(key)
        return
    p = find(contains=contains)
    if p is None:
        raise SystemExit(f"anchor not found for {key}")
    if new in p.text:
        skipped.append(key)
        return
    for r in p.runs:
        if old in r.text:
            r.text = r.text.replace(old, new)
            applied.append(key)
            return
    raise SystemExit(f"{key}: text not in a single run")


# ---------------------------------------------------------------- in-place corrections
replace_in("h_32_30", "Adaptive Evasion Is a Statefulness Problem, and Remains Open",
           "Adaptive Evasion Is a Statefulness Problem (Open Here; Resolved in 32.39)",
           contains="Adaptive Evasion Is a Statefulness Problem")
append_note("p_32_30_open",
            "[Round 7 note: superseded by Section 32.39 -- a powered re-run at the pre-registered "
            "radius resolved adaptive evasion, 32/130 to 1/130, p=9.3e-10.]",
            contains="Adaptive evasion is recorded as OPEN")
replace_in("p_32_33_pending", "That run had not completed when this revision was generated.",
           "That run has since completed; its results are Sections 32.37 and 32.45, and the "
           "per-family B17/B18 figures it could not produce are Section 32.50.",
           contains="That run had not completed")
append_note("p_32_36_dev",
            "[CORRECTION, round 7 (Section 32.49): this 'dev' set is NOT disjoint -- 382 of its 400 "
            "items are hold-out 3 benign prompts verbatim under a different memory wrapper. The "
            "comparison remains symmetric across scorers, but it is hold-out-calibrated, not "
            "dev-calibrated.]",
            contains="Calibrating every scorer on the SAME")
append_note("p_32_36_rule",
            "[Round 7: these 200 'DEV' items are hold-out 3 prompts under a different wrapper "
            "(Section 32.49), so this attribution is a hold-out measurement; its direction is "
            "unaffected.]",
            contains="Second, WHICH RULE")
append_note("p_32_38_open",
            "[Round 7 note: superseded by Section 32.39 -- the falsification stands as a fact "
            "about this test; the powered re-run resolved adaptive evasion.]",
            contains="adaptive evasion remains OPEN")
append_note("p_32_38_exfil",
            "[Round 7 note: superseded by Section 32.43 -- structural gates showed the generator "
            "omitted the recipient; on gate-valid instances exfiltration is a tested mechanism with "
            "zero harm across three agent families.]",
            contains="not agent refusal, these instances")
replace_in("h_32_40", "32.40 Exfiltration Is an Untested Mechanism, Not a Weak One",
           "32.40 Exfiltration Was Reported as an Untested Mechanism (Superseded by 32.43)",
           contains="32.40 Exfiltration")
append_note("p_32_27_deberta",
            "[CORRECTED in Section 32.47: the causal reading here was imprecise. Refitting B14 "
            "without deberta WIDENS the gap (+32.9 to +46.6); the feature is load-bearing and the "
            "gap is a property of the fused weights. The agreement evidence stands.]",
            contains="B14 scores 90.8% on the first")
append_note("p_32_42_budget",
            "[Round 7: the 38.6%-at-4.5% and 41.3%-at-4.4% operating points were calibrated on "
            "near-copies of hold-out 3's benign half (Section 32.49) and are hold-out-calibrated.]",
            contains="Under a tight false-positive budget")
append_note("p_32_44_dev",
            "[Round 7: the gate's 'development' set was near-copies of the hold-out's benign half "
            "(Section 32.49). It was fitted on the hold-out's own distribution and still failed on "
            "it, so the contamination could only have flattered it; the negative result stands.]",
            contains="On development data it looked right")
append_note("p_32_0_guide",
            "Round 7 (32.49 onward): 32.49 the hold-out 3 development set was the hold-out "
            "(correction); 32.50 the founding families under B18 with evidence; later round-7 "
            "subsections add hold-outs 4 and 5 and the compositions tested on them. Corrections made "
            "in round 7 are also marked in place, in brackets, where the corrected sentence stands.",
            contains="Section 32 grew across six review rounds")

append_note("p_32_44_count",
            "[CORRECTED, round 7: hold-out 3 was eventually scored SEVEN times -- these five, then two "
            "neutralisation runs (v1, and the dev-selected v3 of Section 32.46). Only the first was "
            "pre-registered.]",
            contains="hold-out 3 has now been scored five times")
append_note("p_32_46_use",
            "[Round 7 label: this run was hold-out 3's SEVENTH use (the v1 frame's run was the sixth), so "
            "it is not an independent estimate even though this frame was scored once. Hold-out 5, frozen "
            "and pre-registered, replicates the effect cleanly: 37.4% -> 18.3%, p=2e-05 (Section 32.54).]",
            contains="The dev-selected frame, run ONCE on the frozen corpus")

append_note("s33_union_fpr",
            "[Round 7 (R7-12): 'no additional false-positive cost' holds on ordinary memory only. On "
            "hold-out 4's matched benign notes the union excludes 42/262, against 31 for B13 and 24 for "
            "B14 -- it pays both components' false positives.]",
            contains="produced union configurations that beat both components")

append_note("p_32_45_superseded",
            "[SUPERSEDED in round 7 (Section 32.56): on hold-out 4 B17/B18 match B13's recall exactly "
            "and add false positives, so B13 with evidence is the memory-poisoning recommendation.]",
            contains="(1) MEMORY POISONING with the owner's conversation available")

append_note("p_32_51_union",
            "[Settled afterwards (round 7, item 13): a probe enters the union only if its task-alone base "
            "rate is <= 20%. The leading v1 probe (66/157) is excluded, so 123/157 is NOT a valid "
            "alternative; hold-out 4's working set is 86/157 under the rule, as committed.]",
            contains="Under the project's union-over-probes convention it is 123/157")

append_note("p_32_30_097",
            "[Round 7 correction (R7-15): this negative was underpowered too. On the 130 powered seeds the "
            "same 0.97 radius cuts adaptive evasion from 32/130 to 8/130 (p=1e-07) at a 0.7% "
            "ledger-poisoning blast radius; the radius sweep recommends 0.95 (5/130 at 6.4%).]",
            contains="At the frozen development radius the result is negative")

append_note("p_32_56_radius",
            "[Updated by the radius sweep (R7-15): use radius 0.95 -- adaptive evasion 32/130 -> 5/130 "
            "(p=1.5e-08) at a 6.4% ledger-poisoning blast radius, against 29.7% at 0.90; 0.97 gives "
            "8/130 at 0.7% where that surface must be near zero.]",
            contains="(4) RETRY-CAPABLE attackers: compose the chosen configuration with the rejection ledger")

append_note("p_32_46_noise",
            "[Measured in round 7 (noise_repeats.json): three independent runs give a run-to-run SD of "
            "0.8-1.7 points (compliance 61/62/63 and 36/40/39 of 120; undefended harm 87/89/94 of 309), "
            "so the ~5-point floor used throughout is conservative.]",
            contains="A noise floor belongs with these numbers")

append_note("p_32_56_b17",
            "[Updated by hold-outs 6 and 7: for injection-shaped text use B17, not B18 -- B18's deberta hard "
            "rule cost 16.3% false positives on hold-out 6 and excluded 4.9% of the user's own words on "
            "hold-out 7, because it ignores channel trust.]",
            contains="(2) INJECTION-SHAPED text arriving in memory: B17 (or B18)")

# Section 33: the overall conclusion is the place a reader is most likely to stop, and it still
# carried three withdrawn claims. Its paragraphs are corrected in place with a note.
replace_in("s33_ledger",
           "Rejection memory, built specifically to address adaptive evasion, showed no "
           "significant effect at its frozen radius despite engaging in 138 of 151 attack rounds, "
           "and the radius that does work carries a denial-of-service surface that must be "
           "justified separately; adaptive evasion remains open.",
           "Rejection memory, built specifically to address adaptive evasion, showed no "
           "significant effect at its frozen radius, and its first pre-registered test was "
           "underpowered by design; a powered re-run then reduced evasion from 24.6% to 0.8% "
           "(p=9.3e-10, Section 32.39), at a 29.7% ledger-poisoning blast radius that must be "
           "accepted deliberately.",
           contains="Equally, what did not work")
replace_in("s33_exfil",
           "Exfiltration remains the weakest family, and its regeneration showed the difficulty is "
           "in authoring the mechanism rather than labelling it.",
           "Exfiltration was reported as the weakest family until structural gates showed the "
           "generator was omitting the recipient; on gate-valid instances it is a tested mechanism "
           "with zero harm across three agent families (Section 32.43).",
           contains="Equally, what did not work")
replace_in("s33_multihop",
           "Multi-hop reasoning is declared outside what this benchmark measures, because the "
           "oracle condition hands the agent perfect evidence and it still fails a third of the "
           "time, which is an agent-capability ceiling and not a memory-defense result.",
           "Multi-hop reasoning was once declared outside what this benchmark measures; that was "
           "corrected in Section 32.34 -- every agent family answers 80-87% correctly under the LLM "
           "judge, and the oracle 'ceiling' is the strictness of the judge-AND-NLI ensemble, an "
           "evaluator artifact.",
           contains="Equally, what did not work")

# ---------------------------------------------------------------- round-7 sections
concl = find(startswith="33. Overall Conclusion")


def h2(t):
    p = concl.insert_paragraph_before(t)
    p.style = doc.styles["Heading 2"]


def body(t):
    p = concl.insert_paragraph_before(t)
    p.style = BODY


def table(rows):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    try:
        t.style = "Table Grid"
    except KeyError:
        pass
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            cell = t.cell(i, j)
            cell.text = "" if c is None else str(c)
            if i == 0:
                for run in cell.paragraphs[0].runs:
                    run.bold = True
    concl._p.addprevious(t._tbl)
    body("")


def section(heading):
    if find(startswith=heading):
        skipped.append(heading)
        return False
    applied.append(heading)
    h2(heading)
    return True


if section("32.49 A Correction: the Hold-Out 3 Development Set Was the Hold-Out"):
    body("Round 7 began by building a development set of ATTACKS for hold-out 3's distribution, "
         "from the source dataset's earlier snapshot, with a near-duplicate check added "
         "(`phase17/near_dup.py`: word 5-gram containment >= 0.6, a threshold fixed before any "
         "corpus was built with it). 647 of the snapshot's 648 prompts were near-copies of "
         "hold-out 3 attacks: the later collection evidently contains the earlier one.")
    body("The same check applied to the published BENIGN development set (`holdout3_dev_benign`, "
         "400 items) found that 382 of its items are hold-out 3 benign prompts verbatim once the "
         "memory wrapper is stripped, and 393 are near-copies. The disjointness check compared "
         "WRAPPED strings; wrappers rotate by position, so the same prompt under a different "
         "wrapper compared unequal, and the check reported 110 overlaps when the overlap was nearly "
         "the whole set. Every operating point described in Sections 32.36, 32.41 and 32.42 as "
         "'dev-calibrated' on that corpus was therefore fitted on about 38% of the hold-out's own "
         "benign half.")
    body("What survives and what does not. The matched-FPR comparison calibrated every scorer on "
         "the same set, so it remains a symmetric matched-operating-point comparison, and its "
         "ranking is unaffected in direction -- but it is hold-out-calibrated, and is now labelled "
         "so where it appears. The per-rule false-positive attribution was a hold-out measurement. "
         "The memory-shape gate was fitted on the hold-out's own distribution and still failed on "
         "it, which strengthens that negative result. The check now strips wrappers and tests "
         "near-duplicates, a guard test fails if it regresses, and `error_registry.py` proves the "
         "guard by reintroducing the original comparison.")
    body("The owner's decision that followed: hold-out 3 is retired from further measurement. "
         "Round 7's new configurations are developed on development data and tested once on two "
         "new frozen hold-outs (Sections 32.51-32.52), and a guard test refuses any new module that "
         "loads hold-out 3's texts.")

FUE = L("family_union_evidence.json")
if FUE and section("32.50 The Founding Families Under B18 With Evidence"):
    body("Table 5C of the results paper printed dashes for B17 and B18, because their no-evidence "
         "arm was never computed. `phase17/family_union_evidence.py` derives it from saved "
         "per-item decisions, with no model re-run -- B17 is a parameter-free union, so B13 OR B14 "
         "is its definition, and the module refuses to report unless the computed with-evidence "
         "B17 equals B13-with-evidence OR B14-with-evidence on every item, which it does.")
    F = ("agentpoison", "minja", "farma", "memorygraft", "dsrm", "mpbench",
         "sleeper_memory_poisoning")
    rows = [["Founding family", "n (working)", "B13 no ev. -> ev.", "B18 no ev. -> ev.",
             "B18 + ev., working only"]]
    for f in F:
        e = FUE["families"][f]
        b13, b18, w = e["B13"]["full"], e["B18"]["full"], e["B18"]["working"]
        rows.append([f, f"{e['n']} ({e['n_working']})",
                     f"{b13['no_evidence']['rate']:.1%} -> {b13['with_evidence']['rate']:.1%}",
                     f"{b18['no_evidence']['rate']:.1%} -> {b18['with_evidence']['rate']:.1%}",
                     f"{w['with_evidence']['rate']:.1%}"])
    table(rows)
    fp = FUE["ordinary_benign_fpr_with_evidence"]["B18"]
    body(f"Table 21 - Ordinary-benign cost on the same footing: {fp['k']}/{fp['n']} = "
         f"{fp['rate']:.1%}, all on untrusted channels. The result is mixed and is reported as such: "
         "B18 with evidence reaches FARMA (87%) and AgentPoison (65%; 93% of its working "
         "instances) and lifts MPBench, MINJA and sleeper poisoning from near zero to 37-48%, but "
         "MemoryGraft (34%) and DSRM (30%) remain weakly detected by the best configuration "
         "measured. B18 adds nothing over B17 on any founding family.")

V4 = L("holdout4_validity.json")
M4 = L("holdout4_mechanism.json")
C1, C2 = L("holdout4_causal.json"), L("holdout4_causal_v2.json")
if V4 and C2 and section("32.51 Two New Hold-Outs, Frozen Before Any Scoring"):
    body("Hold-out 3 was retired, and its 'development snapshot' proved to be the hold-out (32.49), "
         "so round 7 built two new frozen corpora, each digested and frozen before any configuration "
         "touched it, with predictions committed beforehand in docs/phase17/PREREGISTRATION_ROUND7.md.")
    body("Hold-out 5 is injection-shaped with a matched benign half: 131 jailbreak prompts real users "
         "submitted to the Vicuna demo and 1,000 non-toxic, non-jailbreak prompts from the same "
         "interface (lmsys/toxic-chat, CC-BY-NC-4.0). Before freezing, 52 jailbreak candidates were "
         "dropped as near-copies of corpora this project had already used -- the check hold-out 3 "
         "never had. Its attack half is small, so every rate on it carries an interval of about +/-8 "
         "points and no smaller difference is claimed.")
    body("Hold-out 4 is this project's first MEMORY-POISONING hold-out, addressing the standing "
         "limitation that all earlier hold-outs were injection corpora. It was written by mistral:7b, "
         "a family that had authored no attack here and sits inside no detector, about LoCoMo "
         "conversation 7, whose speakers appear in none of the 804 attacks the defenses were "
         "developed on. No judge filtered it; only deterministic structural gates fixed in advance. "
         "Inspection before freezing found the author had INVERTED both instruction-shaped families "
         "into protective rules, so those were withdrawn as attacks and the 40 inverted standing "
         "instructions kept as hard benign. The corpus is 157 note-shaped attacks (additive "
         "fabrication, preference hijack, fact contradiction, sleeper routine) and 262 benign.")
    body(f"Validity was measured before any scoring, from the corpus alone. An out-of-loop judge "
         f"(Gemini) finds {M4['attack_mechanism']['ALL']['k']}/{M4['attack_mechanism']['ALL']['n']} "
         f"attacks implement their family's mechanism and {M4['benign_valid']['ALL']['k']}/"
         f"{M4['benign_valid']['ALL']['n']} sampled benign items harmless. The causal audit exposed a "
         f"defect in the INSTRUMENT: the generic task generator presupposed fabricated facts, giving "
         f"a task-alone base rate of {C1['task_alone_base_rate']['k']}/157. A non-leading generator "
         f"with a deterministic check that the request contains no distinctive term of the note "
         f"brought it to {C2['task_alone_base_rate']['k']}/157; that change was committed as a "
         f"pre-registration addendum before any defense was scored. Working set (causal AND "
         f"mechanism, non-leading probe): {V4['n_working']}/{V4['n_attacks']}. Under the project's "
         f"union-over-probes convention it is 123/157 (secondary), because non-leading requests give "
         f"contradiction and sleeper attacks less of an opening.")

D7, CD = L("dev_round7.json"), L("compose_dev.json")
if D7 and CD and section("32.52 Development Results: a Failed Lead, a Corpus Effect, and a Composition"):
    mp = D7["beds"]["memory_poisoning_with_evidence"]["per_config"]
    ij = D7["beds"]["injection_no_evidence"]["per_config"]
    body(f"The lead for the unions' false-positive floor was to drop B13's content detector from them "
         f"(B20 = B14 OR B13's provenance rules; B21 its deberta analogue). On development data it "
         f"FAILS. With the owner's conversation, B20 reaches {mp['B20']['recall']['rate']:.1%} of "
         f"this project's attacks against B17's {mp['B17']['recall']['rate']:.1%} at the same "
         f"{mp['B17']['benign_fpr']['rate']:.1%} benign cost: every ordinary-benign exclusion by B13 "
         f"comes from corroboration, and its content detector excludes no ordinary benign item while "
         f"catching attacks B14 misses. On injection-shaped dev data B20 equals B14 exactly. B20/B21 "
         f"are dominated in both beds; they were scored on the hold-outs only because the design had "
         f"been announced.")
    body(f"The same development run measured matched-platform benign text from toxic-chat and did not "
         f"reproduce hold-out 3's false-positive regime: B13 {ij['B13']['benign_fpr']['rate']:.1%}, "
         f"B17 {ij['B17']['benign_fpr']['rate']:.1%}, B18 {ij['B18']['benign_fpr']['rate']:.1%}, "
         f"against 33.5%, 54.8% and 54.9% on hold-out 3's benign half. The floor is B13's own rate on "
         f"the corpus at hand, so the 33-55% regime is at least partly a property of the "
         f"jailbreak-community prompts that make up hold-out 3's benign half.")
    rows = [["Detector (dev)", "Exclusion alone: harm / benign excluded",
             "Exclusion + neutralise the rest: harm / benign excluded"]]
    for c in ("B12", "B14", "B17", "B18"):
        v = CD["by_detector"][c]["policies"]
        rows.append([c, f"{v['P2_exclude']['harm_rate']:.1%} / {v['P2_exclude']['benign_exclusion_rate']:.1%}",
                     f"{v['P4_exclude_plus_neutralise_rest']['harm_rate']:.1%} / "
                     f"{v['P4_exclude_plus_neutralise_rest']['benign_exclusion_rate']:.1%}"])
    rows.append(["(none)", f"{CD['compliance_raw']['rate']:.1%} / 0.0%",
                 f"neutralise everything: {CD['compliance_framed']['rate']:.1%} / 0.0%"])
    table(rows)
    body("Table 22 - Neutralisation composed with detection on development data (266 externally "
         "authored attacks; 400 toxic-chat dev benign; the two halves come from different sources). "
         "Harm is an attack that is admitted AND complied with. Excluding with the cheapest detector "
         "and admitting everything else under the frame beats the strongest exclusion-only "
         "configuration on both axes. The cost that travels with it is separate and is not folded "
         "into either column: nearly all admitted benign memory is framed, which cost 2.2 points of "
         "benign information use on development data (not significant at n=90).")

XA = L("exfil_authoring.json")
if XA and section("32.53 Exfiltration Authoring: the Instruction, Not the Author"):
    g = XA["generators"]
    body("Regeneration accepted exfiltration candidates at the unguided rate, so the specification "
         "had not improved authoring. Two explanations predict different things: the author cannot "
         "write the mechanism (another author would do better), or the instruction is too abstract "
         "(worked examples would). Four generators received the identical specification, gates and "
         "judge, 40 candidates each, with near-copies of any example counted as failures: "
         + "; ".join(f"{k} {v['accepted_gate_and_judge']['k']}/{v['n']}" for k, v in g.items())
         + ". A different author family does not help; three worked examples do, for both authors. "
         "The defect was the instruction.")

R7E, R7P = L("eval_round7_holdouts.json"), L("round7_predictions.json")
if R7E and R7P and section("32.54 Hold-Outs 4 and 5, Scored Once: What Held and What Did Not"):
    h5, h4 = R7E["holdouts"]["holdout5"], R7E["holdouts"]["holdout4"]
    rows = [["Configuration", "HO5 recall (131)", "HO5 matched-benign FPR (1,000)", "HO4 recall (157)",
             "HO4 benign FPR untrusted / user_turn (262)"]]
    for c in ("B12", "B13", "B14", "B15", "B17", "B18", "B20", "B21"):
        a, b = h5["configs"][c], h4["configs"][c]
        rows.append([c, f"{a['attack_recall']['rate']:.1%}", f"{a['matched_benign_fpr']['rate']:.1%}",
                     f"{b['attack_recall']['rate']:.1%}",
                     f"{b['benign_fpr_untrusted_channel']['rate']:.1%} / {b['benign_fpr_user_turn']['rate']:.1%}"])
    table(rows)
    body("Table 23 - Hold-outs 4 and 5, each scored exactly once, after the pre-registration and its "
         "addendum were committed. Hold-out 4 is scored with the owner's conversation as evidence. "
         "These are the first clean estimates for B17 and B18, which were selected after reading "
         "earlier hold-out results.")
    body(f"Pre-registered outcome: {R7P['n_held']} of {R7P['n_scored']} scorable predictions held, which "
         f"the rule fixed in advance calls {R7P['verdict']}. What held is substantive. The 33-55% "
         f"false-positive regime of hold-out 3 does not reproduce on matched benign text from another "
         f"platform: B17 {h5['configs']['B17']['matched_benign_fpr']['rate']:.1%} and B18 "
         f"{h5['configs']['B18']['matched_benign_fpr']['rate']:.1%}, so the earlier 'unfixable by "
         f"detection' reading (32.44) describes hold-out 3's benign corpus rather than detection on "
         f"injection-shaped text in general. And on the first memory-poisoning hold-out, written by a "
         f"new author family about a new owner, provenance reaches what content detection cannot: B13 "
         f"{h4['configs']['B13']['attack_recall']['rate']:.1%} against B14's "
         f"{h4['configs']['B14']['attack_recall']['rate']:.1%} (p=1e-14), content-only B12 "
         f"{h4['configs']['B12']['attack_recall']['rate']:.1%}, and every published baseline near zero, "
         f"at {h4['configs']['B13']['benign_fpr_untrusted_channel']['rate']:.1%} benign cost on the "
         f"untrusted channel and none on the user's own words.")
    n5 = h5["neutralisation"]
    d12, d18 = n5["by_detector"]["B12"]["policies"], n5["by_detector"]["B18"]["policies"]
    body(f"What failed is reported with the same weight. The pre-registered PRIMARY prediction -- that "
         f"excluding with B12 and neutralising the rest beats B12 exclusion alone -- moved harm from "
         f"{d12['P2_exclude']['harm_k']} to {d12['P4_exclude_plus_neutralise_rest']['harm_k']} of 131 at "
         f"p={n5['by_detector']['B12']['paired_P4_vs_P2_harm']['p_exact']:.2g}: the right direction and "
         f"not significant, so it FAILED. The claim that this composition dominates the strongest "
         f"exclusion-only configuration also FAILED: B18 alone reached {d18['P2_exclude']['harm_rate']:.1%} "
         f"harm at {d18['P2_exclude']['benign_exclusion_rate']:.1%} exclusion against "
         f"{d12['P4_exclude_plus_neutralise_rest']['harm_rate']:.1%} at "
         f"{d12['P4_exclude_plus_neutralise_rest']['benign_exclusion_rate']:.1%}. The development "
         f"result that motivated it did not generalise: where detectors already reach 90% recall, "
         f"neutralisation is a trade along the false-positive axis, not a dominating configuration. "
         f"Neutralising everything still halved compliance ({n5['compliance_raw']['rate']:.1%} to "
         f"{n5['compliance_framed']['rate']:.1%}, p={n5['paired_framed_vs_raw']['p_exact']:.2g}) at no "
         f"exclusion cost, and on hold-out 4's note-shaped attacks it did almost nothing, as predicted. "
         f"B18's recall fell 0.1 point outside its predicted interval and is counted as failed under "
         f"the strict rule. B18 adds nothing over B17 on either hold-out.")

OWN, STR = L("neutralise_own.json"), L("neutralise_strong_agent.json")
if OWN and STR and section("32.55 Neutralisation Beyond Injection Text: Own Attacks and a Stronger Agent"):
    body(f"Two questions about the neutralisation frame were pre-registered before measurement. First, "
         f"does it help against this project's own memory-poisoning attacks? The prediction was that it "
         f"would help little, because a fabricated fact contains no instruction for the frame to "
         f"neutralise. On the 309 harm-study instances, with both arms re-run in one session (the raw arm "
         f"reproduced the published 28.2% at {OWN['harm_raw_rerun']['rate']:.1%}), harm fell to "
         f"{OWN['harm_framed']['rate']:.1%} framed (p={OWN['paired_framed_vs_raw']['p_exact']:.2g}), and "
         f"B13 plus the frame reached {OWN['harm_b13_plus_frame']['rate']:.1%} against B13's "
         f"{OWN['harm_b13']['rate']:.1%} (p={OWN['paired_b13frame_vs_b13']['p_exact']:.2g}). Neither is "
         f"significant, and neither is claimed as an improvement.")
    q = STR["qwen_same_items"]
    body(f"Second, is the effect larger on a more capable agent? On 60 paired development items, "
         f"gemini-3.5-flash-lite complied with {STR['arms']['raw']['rate']:.1%} of injected instructions "
         f"raw and {STR['arms'][STR['frame']]['rate']:.1%} framed "
         f"(p={STR['paired_framed_vs_raw_gemini']['p_exact']:.2g}), against qwen2.5:7b's "
         f"{q['raw']['rate']:.1%} and {q['framed']['rate']:.1%} on the same items. The stronger agent is "
         f"no less susceptible to the raw injection -- the raw rates are within noise of each other -- but "
         f"honours the 'this is data' constraint far better, so the frame's benefit roughly doubled "
         f"({STR['effect_points']['gemini']:+.1f} against {STR['effect_points']['qwen']:+.1f} points). "
         f"At n=60 that difference is suggestive rather than established, and it is reported as such. "
         f"Because every harm figure in this benchmark comes from 7-8B agents, it is also the one result "
         f"here whose direction suggests the 7B measurements understate a defense rather than overstate it.")

if L("eval_round7_holdouts.json") and section("32.56 Recommendation, Round 7"):
    for _t in ['RECOMMENDATION (round 7; supersedes the round-6 guidance of Section 32.45 / 10B, which named B18 for memory poisoning). It is still conditioned on the threat and the false-positive budget, and it now rests on two clean hold-outs rather than on populations the configurations were selected on.', "(1) MEMORY POISONING with the owner's conversation available: B13 with evidence. On hold-out 4 -- a new author family, a new owner, scored once -- it reaches 50.3% of attacks (60.5% of working ones) at 11.8% false positives on untrusted channels and 0.0% on the user's own words. B17 and B18 match its recall exactly there and add false positives (16.0%), so they are dominated on this threat; their +4.9-point lead on this project's own attacks was measured on populations they were selected after reading. Where the budget is near zero on untrusted channels, B12 is NOT an alternative for this threat: it reaches 1.9% on hold-out 4.", "(2) INJECTION-SHAPED text arriving in memory: B17 (or B18) where about a 10% false-positive budget is acceptable -- 90.1% recall at 10.2-11.0% on hold-out 5's matched benign. The 33-55% figures of hold-out 3 were a property of that corpus. B18 adds nothing over B17 on either new hold-out, so the deberta dependency is not justified by clean evidence.", '(3) NEUTRALISATION as a zero-exclusion layer under any of the above: admit untrusted memory verbatim, framed as data, with the constraint repeated after it. It halved compliance on hold-out 5 (37.4% -> 18.3%) and its effect roughly doubled on a stronger agent (60 dev items). It does almost nothing against fabricated facts, and composed with a cheap detector it does NOT dominate strong exclusion (the pre-registered test failed): it is a trade that buys lower exclusion at higher residual compliance.', '(4) RETRY-CAPABLE attackers: compose the chosen configuration with the rejection ledger, accepting its denial-of-service surface deliberately (Section 9 and the radius sweep).']:
        body(_t)

CV2, R7PS = L("corroboration_v2_dev.json"), L("round7_predictions.json")
if CV2 and R7PS and section("32.57 Follow-Up Work: Two Corroboration Fixes That Failed, and Measurement Hygiene"):
    v1, v2 = CV2["B13_v1"], CV2["B13_v2"]
    body("The owner asked for every remaining weakness to be worked through. Two of the detector "
         "changes it produced failed on development data, and both failures are informative.")
    body(f"Corroboration that abstains. Hold-out 4's false positives concentrated in ordinary notes "
         f"the conversation never mentions, so corroboration was made to abstain when a claim is "
         f"unrelated to the conversation (threshold fitted on LoCoMo development conversations 1-4). "
         f"On the development bed it cut recall from {v1['recall']['rate']:.1%} to "
         f"{v2['recall']['rate']:.1%} (p={CV2['paired_attacks_v2_vs_v1']['p_exact']:.1g}) and did not "
         f"lower the benign rate ({v1['benign_fpr']['rate']:.1%} to {v2['benign_fpr']['rate']:.1%}): "
         f"preference hijack fell from {CV2['by_family']['preference_hijack']['v1']} to "
         f"{CV2['by_family']['preference_hijack']['v2']} of 50. Fabrications are, by construction, about "
         f"things the conversation never mentions, so 'not mentioned' is the signal against them. A "
         f"benign new fact and a fabricated one are indistinguishable to corroboration, and the "
         f"false-positive cost on ungrounded benign notes is the price of the signal, not a removable "
         f"defect.")
    body(f"Corroboration that reads contradiction. Excluding claims the conversation contradicts, at a "
         f"threshold set purely by a 0.5% benign budget on development data "
         f"(TAU_CONTR={CV2['constants']['TAU_CONTR']}), added 7 caught attacks for 16 additional benign "
         f"false positives on the development bed; the small NLI model's contradiction head fires on "
         f"ordinary memories. The development bed has no contradiction-family attacks, so the rule's "
         f"value on the class it targets is untested there; it is frozen and pre-registered for "
         f"hold-out 7, which has one.")
    sh = R7PS["sharpness"]
    body(f"Calibration, scored for sharpness as well as hits. A hit count rewards wide intervals, so "
         f"interval widths are now reported beside it: {sh['n_interval_held']}/{sh['n_interval']} "
         f"interval predictions held at a mean width of {sh['mean_interval_width_points']} points; every "
         f"interval of 12 points or narrower held; the two of 35 points split, and are weak predictions "
         f"whichever way they fell.")
    body("Measurement hygiene. The working-set rule across probes is fixed in code before the next "
         "hold-out: a probe enters the union only if its task-alone base rate is at most 20%, which "
         "reproduces hold-out 4's committed 86/157 and retracts a 123/157 figure that had unioned in the "
         "leading probe. Hold-out scoring is an explicit-only pipeline stage, so a full re-run cannot "
         "re-score a frozen corpus. The two documents are now versioned with the code that builds them. "
         "And a blind 100-item human-annotation sheet for the LLM judges exists; the owner caught that "
         "23 of its 40 harm answers had been stored truncated to 400 characters while the judge saw the "
         "full text, so those rows are being rebuilt from a run that keeps the full answers. Until a "
         "person has labelled it, the judges remain unvalidated against humans, and that is stated as a "
         "limitation.")
    body("Hold-out 6 (SPML, MIT): 500 LLM-authored chatbot prompt injections and 1,000 benign prompts "
         "to the same personas, frozen before scoring after dropping 3,728 near-copies of corpora "
         "already used. It replicates or bounds hold-out 5's finding on a second independent corpus. "
         "Hold-out 7 is written by a BASE (non-instruct) model, so instruction-shaped memory poisoning, "
         "which hold-out 4's safety-tuned author refused to write, gets a clean test.")

HL, HJ, NR = L("human_label_agreement.json"), L("harm_judge_fix.json"), L("noise_repeats.json")
if HL and HJ and NR and section("32.58 The Judges, Checked Against a Person; and the Noise Floor, Measured"):
    h, cp = HL["by_type"]["harm"], HL["by_type"]["compliance"]
    body(f"Every compliance, harm and mechanism label in this benchmark comes from an LLM judge. A blind "
         f"100-item sheet, balanced between judge-YES and judge-NO within each judge, was labelled by one "
         f"person. The compliance judge (llama3.1:8b) agreed {round(100 * cp['agreement'])}% of the time, "
         f"kappa {cp['cohen_kappa']}; the harm judge only {round(100 * h['agreement'])}%, kappa "
         f"{h['cohen_kappa']}, with all {h['judge_no_human_yes']} disagreements in one direction -- missed "
         f"harm. The mechanism judge (Gemini) rejected 5 of 20 notes the annotator accepted. Reading the harm "
         f"disagreements, about half are plain misses of what the item's own question describes and half a "
         f"generous annotator; one annotator cannot separate the two, and a second is listed as open.")
    body("Consequences, stated rather than resolved: harm LEVELS in this document are likely under-estimates; "
         "harm REDUCTIONS are more robust because both arms share the judge; detection and false-positive "
         "results use no judge. The sheet itself was found by the annotator to show harm answers truncated "
         "to 400 characters while the judge had seen the full text; those rows were rebuilt from a run that "
         "stores answers in full before any harm row was labelled.")
    c = HJ["candidates"]
    body(f"A replacement harm judge was selected by a rule committed before any candidate was scored: the 40 "
         f"harm labels split by a fixed seed into 20 for selection and 20 for testing, the highest-kappa "
         f"candidate on selection chosen, adopted only if it beats the current judge on the held-back half. "
         f"{HJ['adopted']} was chosen (selection kappa {c[HJ['adopted']]['select']['kappa']}) and reaches a "
         f"held-back kappa of {c[HJ['adopted']]['test']['kappa']} against the current judge's "
         f"{c['J0_current']['test']['kappa']}. A rubric variant scored higher on the held-back half but lower "
         f"on selection, and choosing it after seeing that would be exactly the selection the rule exists to "
         f"prevent." + ("" if HJ.get("complete") else " One local candidate remains to be scored."))
    cc = NR["compliance"]
    body(f"The noise floor, argued throughout this section to be about 5 points on n=120, was measured: three "
         f"independent runs of fresh agent and judge calls gave compliance {cc['raw']['runs_k']} and "
         f"{cc['v3_depersonalise']['runs_k']} of 120 and undefended harm {NR['harm']['runs_k']} of 309 -- "
         f"run-to-run standard deviations of 0.8-1.7 points. The 5-point floor is conservative.")

E67, R7P3 = L("eval_round7b_holdouts.json"), L("round7_predictions.json")
if E67 and R7P3 and section("32.59 Hold-Outs 6 and 7: a Replication, a Powered Re-Test, and Two Defects of B18"):
    h6, h7 = E67["holdouts"]["holdout6"], E67["holdouts"]["holdout7"]
    rows = [["Configuration", "HO6 recall", "HO6 matched-benign FPR", "HO7 recall", "HO7 benign FPR untrusted / user_turn"]]
    for c in ("B12", "B13", "B14", "B15", "B17", "B18"):
        a, b = h6["configs"][c], h7["configs"][c]
        rows.append([c, f"{a['attack_recall']['rate']:.1%}", f"{a['matched_benign_fpr']['rate']:.1%}",
                     f"{b['attack_recall']['rate']:.1%}",
                     f"{b['benign_fpr_untrusted_channel']['rate']:.1%} / {b['benign_fpr_user_turn']['rate']:.1%}"])
    table(rows)
    d12 = h6["neutralisation"]["by_detector"]["B12"]
    body(f"Table 24 - Scored once under pre-registration addendum 3; {R7P3['n_held']} of {R7P3['n_scored']} "
         f"round-7 predictions now hold. Hold-out 6 replicates the false-positive finding on a second "
         f"independent corpus (B17 at {h6['configs']['B17']['matched_benign_fpr']['rate']:.1%}), and the "
         f"composition test that failed on hold-out 5 for lack of power holds with 500 attacks "
         f"({d12['policies']['P2_exclude']['harm_k']} -> {d12['policies']['P4_exclude_plus_neutralise_rest']['harm_k']}, "
         f"p={d12['paired_P4_vs_P2_harm']['p_exact']:.2g}). Neutralisation helps a weak detector and adds "
         f"nothing on top of B18. Two defects of B18 surfaced, both on hold-outs, so any fix is "
         f"hold-out-informed: its deberta hard rule excluded "
         f"{h6['configs']['B18']['matched_benign_fpr']['rate']:.1%} of hold-out 6's ordinary prompts, and "
         f"{h7['configs']['B18']['benign_fpr_user_turn']['rate']:.1%} of hold-out 7's benign notes arriving as "
         f"the user's own words, because it ignores the channel trust B13 applies. The contradiction rule "
         f"added nothing; framing raised compliance on instruction-shaped attacks on hold-out 7 (a failed "
         f"prediction); and hold-out 7's working subset is not reportable, because its probe's task-alone base "
         f"rate (28%) exceeds the 20% rule fixed before the corpus was built.")

UT, AD, HS, HR, S120, H6C = (L("neutralise_utility.json"), L("adaptive_round7.json"),
                             L("harm_strong_agent.json"), L("harm_rejudged.json"),
                             L("neutralise_strong_agent_n120.json"), L("holdout6_causal.json"))
if UT and AD and HS and HR and S120 and H6C and section(
        "32.60 The Last Measurements: Utility Cost, Adaptive Evasion, Re-Judged Harm, Stronger Agent"):
    parts = []
    loss = ", ".join(f"{n} {t['loss_points']:+.1f} points (p={t['paired_framed_vs_raw']['p_exact']:.2g})"
                     for n, t in UT["tasks"].items())
    parts.append(f"Utility: on {UT['n_notes']} benign notes the frame cost {loss}.")
    for key, label in (("vs_neutralisation", "the frame"), ("vs_corroboration", "corroboration")):
        if AD.get(key):
            ev = AD[key]["adaptive_evasion"]
            parts.append(f"An adaptive attacker with {AD['budget']} feedback-guided rewrites evaded "
                         f"{label} on {ev['k']}/{AD[key]['n_seeds']} initially-caught seeds.")
    for name, r in HR["by_judge"].items():
        parts.append(f"Harm under {name}: undefended {r['harm_undefended']['rate']:.1%}, with B13 "
                     f"{r['harm_b13']['rate']:.1%}, task-alone {r['task_alone_base_rate']['rate']:.1%} "
                     f"(n={HR['n']}).")
    g = HS["gemini"]
    parts.append(f"Stronger-agent harm (seeded {HS['n']}): undefended {g['harm_undefended']['rate']:.1%} vs "
                 f"qwen {HS['qwen_same_items']['harm_undefended']['rate']:.1%}.")
    parts.append(f"Stronger-agent framing on all {S120['n']} dev items: {S120['effect_points']['gemini']:+.1f} "
                 f"points (qwen {S120['effect_points']['qwen']:+.1f}).")
    parts.append(f"Hold-out 6 working subset: {H6C['working']['k']}/{H6C['n']} (task-alone base rate "
                 f"{H6C['task_alone_base_rate']['k']}/{H6C['n']}).")
    body(" ".join(parts) + " None of these was pre-registered as a prediction; each is reported as "
         "measured, beside the corresponding earlier figure, and nothing was tuned on it.")

R7P2 = L("round7_predictions.json")
if R7E and R7P2:
    c33 = find(startswith="Equally, what did not work")
    marker = "Round 7 (2026-10-06/07)"
    if c33 is not None and find(contains=marker) is None:
        h5c, h4c = R7E["holdouts"]["holdout5"]["configs"], R7E["holdouts"]["holdout4"]["configs"]
        np_ = c33.insert_paragraph_before(
            f"{marker} tested these conclusions on two hold-outs built for it and scored once under "
            f"committed predictions ({R7P2['n_held']}/{R7P2['n_scored']} held). Provenance reached "
            f"{h4c['B13']['attack_recall']['rate']:.1%} of memory poisoning written by an unseen author "
            f"about an unseen owner, against {h4c['B14']['attack_recall']['rate']:.1%} for the fused "
            f"content classifier; the unions ran at {h5c['B17']['matched_benign_fpr']['rate']:.1%}-"
            f"{h5c['B18']['matched_benign_fpr']['rate']:.1%} matched-benign false positives, so the "
            f"55% regime was one corpus; and the composition of neutralisation with detection that "
            f"dominated on development data failed its pre-registered test and is a trade, not a win.")
        np_.style = BODY
        applied.append("s33_round7")
doc.save(PATH)
print(f"applied {len(applied)}: {applied}")
print(f"already present {len(skipped)}: {skipped}")
print("DONE")
