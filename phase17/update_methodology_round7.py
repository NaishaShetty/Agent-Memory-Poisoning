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

doc.save(PATH)
print(f"applied {len(applied)}: {applied}")
print(f"already present {len(skipped)}: {skipped}")
print("DONE")
