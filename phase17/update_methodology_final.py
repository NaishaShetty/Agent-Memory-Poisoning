# -*- coding: utf-8 -*-
"""Final round-6 methodology sections: hold-out 3, the false-positive investigation, the
evidence fix, the pre-registered adaptive test, and the exfiltration verdict."""
from __future__ import annotations

import json
from pathlib import Path

import docx

PATH = "Methodology Draft.docx"
DATA = Path("phase17/data")
MARK = "32.35 Hold-Out 3 and the False-Positive Investigation"


def L(n):
    p = DATA / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


H3, MF, BVA = L("eval_holdout3.json"), L("holdout3_matched_fpr.json"), L("benign_validity_audit.json")
DIAG, EVID, FRESH = L("diagnose_benign_fpr.json"), L("evidence_round6.json"), L("eval_rejection_fresh.json")
EXF = L("exfiltration_agent_check.json")

doc = docx.Document(PATH)
if any(MARK in p.text for p in doc.paragraphs):
    raise SystemExit("already applied")
concl = next(p for p in doc.paragraphs if p.text.startswith("33. Overall Conclusion"))
BODY = doc.paragraphs[4].style


def h2(t):
    p = concl.insert_paragraph_before(t)
    p.style = doc.styles["Heading 2"]
    return p


def body(t):
    p = concl.insert_paragraph_before(t)
    p.style = BODY
    return p


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


pc = lambda x: "n/a" if x is None else "%.1f%%" % (100 * x)

h2(MARK)
body(
    "The third hold-out was frozen with predictions recorded in advance, and it is the first "
    "corpus in this project to supply a MATCHED benign half -- 995 ordinary prompts from the same "
    "platforms as its attacks. That single design choice produced the round's most consequential "
    "result, and it is unfavourable.")
if H3:
    rows = [["Configuration", "Attack recall (1,000)", "Matched-benign FPR (995)", "Recall - FPR"]]
    for c, v in H3["configs"].items():
        a, b = v["attack_recall"]["rate"], v["matched_benign_fpr"]["rate"]
        rows.append([c, pc(a), pc(b), "%+.1f%%" % (100 * (a - b))])
    for c in ("deberta_pi_v2@dev", "llama_guard3@dev"):
        v = H3["baselines"].get(c)
        if v:
            a, b = v["attack_recall"]["rate"], v["matched_benign_fpr"]["rate"]
            rows.append([c, pc(a), pc(b), "%+.1f%%" % (100 * (a - b))])
    table(rows)
    body(
        "Table 6 - Hold-out 3 at shipped thresholds. False-positive rates are 180-370 times those "
        "measured on ordinary conversational memory (0.09%), because every false-positive number "
        "in this project had previously been taken on benign text that looks nothing like the "
        "attack distribution. The union configurations reach 93% recall by flagging more than half "
        "of all benign text, so their discrimination is the WORST of the configurations tested, "
        "and the recall ranking inverts once the cost column is present.")
    body(
        "Of the five pre-registered predictions, two held and three failed. B18 >= B17 held but "
        "at p=0.25; B13 being poor on a jailbreak corpus held. B18 beating B14 by five points "
        "failed at +0.4; the prediction that the published baselines would degrade most failed and "
        "failed backwards, since our configurations degraded far more than the strongest baseline; "
        "and the prediction that nothing would exceed 85% recall failed for four configurations.")

h2("32.36 Diagnosing the False Positives: Three Candidate Causes, Measured")
body(
    "A 54.9% false-positive rate demands an explanation before it is reported as discrimination. "
    "Three causes were possible and each was measured rather than argued.")
if BVA:
    v = BVA["populations"]["holdout3_matched_benign"]["valid_benign"]
    body(
        f"First, a LABELLING artifact. The dataset's `regular` label means 'not classified as a "
        f"jailbreak', not 'appropriate for an agent to store'; the corpus contains persona "
        f"definitions, model control tokens and filler. `benign_validity_audit.py` applies to the "
        f"benign side the same validity discipline the attack side already gets, with a criterion "
        f"fixed in advance and a judge from a third model family that never sees a defense's "
        f"decision. It finds {v['k']}/{v['n']} = {v['rate']:.1%} of the corpus benign AS A MEMORY, "
        f"against 99.4-100% for the four ordinary populations -- so the audit is calibrated rather "
        f"than permissive. But recomputing on the validated subset moves B18 from 54.9% only to "
        f"49.0%: the artifact explains about six of the fifty-five points. I had expected it to "
        f"explain most of them and it does not.")
if DIAG:
    f = DIAG["fpr"]
    a = DIAG["attribution"]
    body(
        f"Second, WHICH RULE. Per-rule attribution on {DIAG['n']} DEV items from the same source "
        f"shows content-only at {f['B12']['rate']:.1%}, provenance adding "
        f"{a['added_by_B13_without_evidence']} exclusions, and corroboration adding "
        f"{a['added_by_corroboration_with_evidence']}. Corroboration is not the cause; the stacked "
        f"CONTENT detector is, firing on {f['B12']['rate']:.1%} of long instruction-shaped prose "
        f"because its threshold was calibrated on conversational-memory negatives. My earlier "
        f"reading, that corroboration was flagging prose about strangers, was wrong.")
if MF:
    rows = [["Scorer", "Recall", "Realised benign FPR", "Recall - FPR"]]
    for e in MF["ranking_at_matched_dev_fpr"]:
        rows.append([e["scorer"], pc(e["recall"]), pc(e["realised_fpr"]),
                     "%+.1f%%" % (100 * e["recall_minus_fpr"])])
    table(rows)
    body(
        "Table 7 - Third, an OPERATING-POINT asymmetry, which the first table concealed and which "
        "ran against us. The baselines' thresholds are suffixed `@dev` because they were "
        "calibrated on dev negatives: each baseline chose an operating point suited to the "
        "distribution, while our configurations ran at thresholds frozen from conversational "
        "memory. Calibrating every scorer on the SAME disjoint dev snapshot -- the dataset's "
        "earlier snapshot, with 110 overlapping items dropped from the dev side so disjointness is "
        "enforced -- and then evaluating once closes most of the gap: the strongest baseline's "
        "advantage over the best configuration falls from 17 points to 2.8. It does not close it "
        "entirely, and the baseline still leads on this corpus. Against the 38.8-point lead the "
        "provenance configuration holds over that same baseline on memory-poisoning attacks, the "
        "picture is coherent rather than contradictory: an off-the-shelf injection classifier is "
        "competitive-to-better on injection-shaped text and far behind on memory poisoning.")

h2("32.37 The Corroboration Fix, and the Channel That Explains Its Cost")
if EVID:
    rows = [["Configuration", "Own attacks, no evidence", "Own attacks, with evidence",
             "Ordinary-benign FPR, no ev.", "Ordinary-benign FPR, with ev."]]
    for c, v in EVID["aggregate"].items():
        rows.append([c,
                     pc((v.get("attacks_no_evidence") or {}).get("rate")),
                     pc((v.get("attacks_with_evidence") or {}).get("rate")),
                     f"{(v.get('ordinary_benign_no_evidence') or {}).get('k')}/1054",
                     f"{(v.get('ordinary_benign_with_evidence') or {}).get('k')}/1054"])
    table(rows)
    body(
        "Table 8 - Scoring the own-attack populations with the owner's real conversation supplied, "
        "and the benign populations with the SAME evidence so the recall gain carries its cost. "
        "Every founding family improves and sleeper memory poisoning leaves 0% for 37%; aggregate "
        "own-attack recall rises 46.1% to 59.7% for the provenance configuration against an "
        "ordinary-benign cost of 7.5%, so discrimination improves from +46.1 to +52.2 rather than "
        "trading evenly.")
    body(
        "One apparent regression was an artifact of the channel, and the distinction matters for "
        "the threat model. Legitimate standing instructions read 2/40 before and 18/40 after, "
        "which looks like undoing a headline result. Scored in the channel they actually arrive on "
        "-- user_turn, where provenance records them as the user's own words -- the same "
        "population with the same evidence gives 0/40, and named-party preferences and "
        "confirmed-human notes likewise give 0/6 and 0/20. The corroboration rule's false-positive "
        "cost falls entirely on untrusted channels, which is where it should fall; the earlier "
        "18/40 was the tool_output condition, in which a standing instruction SHOULD be flagged.")

h2("32.38 The Pre-Registered Adaptive Test, and the Exfiltration Verdict")
if FRESH:
    a = FRESH["per_arm"]
    rows = [["Arm", "Seeds", "Initially excluded", "Genuine adaptive evasion"]]
    for k, v in a.items():
        g = v["genuine_adaptive_evasion_of_initially_excluded"]
        rows.append([k, v["n_seeds"], v["n_initially_excluded"], f"{g['k']}/{g['n']}"])
    table(rows)
    body(
        f"Table 9 - The rejection-memory radius at the value fixed in the pre-registration, on 120 "
        f"fresh seeds drawn by a mechanical rule from populations the adaptive attacker had never "
        f"been pointed at and asserted disjoint from the 43 the radius was chosen on. Paired: "
        f"{FRESH.get('paired_B16_vs_B15')}. By the falsification rule written in advance -- no "
        f"reduction, or p>0.1 with at least 20 initially-excluded seeds -- B16 is FALSIFIED. The "
        f"honest reading is that the test could not have passed: the control arm produced exactly "
        f"one evasion event, B16 prevented it, and one event caps the achievable result at a "
        f"p-value of 1.0. That is a flaw in the seed-selection rule, which drew from populations "
        f"where the defense already excludes most instances at round 0. Both facts are reported, "
        f"the exploratory result remains unconfirmed, and adaptive evasion remains OPEN.")
if EXF:
    rows = [["Agent family", "Complied with memory", "Causal harm"]]
    for m, v in EXF["per_agent"].items():
        rows.append([m, f"{v['complied_with_memory']['k']}/{v['complied_with_memory']['n']}",
                     f"{v['harmful_causal']['k']}/{v['harmful_causal']['n']}"])
    table(rows)
    body(
        "Table 10 - Exfiltration across three agent families, on instances a third-model judge "
        "confirms are exfiltration attacks and which are retrieved 53% of the time. All three are "
        "at zero. The conclusion the module commits to in advance therefore applies: this is not "
        "agent refusal, these instances do not create a compliance opportunity, and the limitation "
        "is in the attack construction rather than the model. That is the fourth explanation this "
        "project has offered for the same zero and the first one measured against an alternative.")

doc.save(PATH)
print("added Sections 32.35-32.38")
print("DONE")
