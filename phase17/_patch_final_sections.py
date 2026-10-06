# -*- coding: utf-8 -*-
"""Final methodology sections: neutralisation, the deberta ablation, and the calibration test."""
from __future__ import annotations

import json
from pathlib import Path

import docx

D = Path("phase17/data")


def L(n):
    p = D / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


NV = L("neutralise.json")
N2 = L("neutralise_v2.json")
AB = L("b14_ablate_deberta.json")
CA = L("eval_calibration2.json")
ER = L("error_registry.json")

P = "Methodology Draft.docx"
doc = docx.Document(P)
MARK = "32.46 Neutralisation: Addressing the Unresolved Regime on a Different Axis"
if any(MARK in p.text for p in doc.paragraphs):
    raise SystemExit("already applied")
concl = next(p for p in doc.paragraphs if p.text.startswith("33. Overall Conclusion"))
BODY = doc.paragraphs[4].style


def h2(t):
    q = concl.insert_paragraph_before(t)
    q.style = doc.styles["Heading 2"]
    return q


def body(t):
    q = concl.insert_paragraph_before(t)
    q.style = BODY
    return q


def table(rows):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    try:
        t.style = "Table Grid"
    except KeyError:
        pass
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            cell = t.cell(i, j)
            cell.text = str(c)
            if i == 0:
                for run in cell.paragraphs[0].runs:
                    run.bold = True
    concl._p.addprevious(t._tbl)
    body("")


# ------------------------------------------------------------------ neutralisation
h2(MARK)
body(
    "Section 32.44 established that the hold-out 3 false-positive rate is not merely unfixed but "
    "unfixable by detection: the corpus's benign and malicious halves are structurally "
    "indistinguishable, and a memory-shape gate made discrimination worse. That closes one axis "
    "and opens another. Every configuration in this project chooses between admitting a memory "
    "and excluding it, but the harm a poisoned memory does is not caused by its presence -- it "
    "is caused by the agent treating its content as direction. So the candidate is admitted "
    "VERBATIM and framed as recorded data rather than instruction. Nothing is excluded, so the "
    "false-positive rate is zero by construction, and the question becomes whether the agent "
    "still complies.")
if N2:
    rows = [["Frame", "Attack compliance", "Benign information used", "Compliance drop",
             "Utility cost"]]
    for n, f in N2["frames"].items():
        rows.append([n, f"{f['attack_compliance']['rate']:.1%}",
                     f"{f['benign_information_used']['rate']:.1%}",
                     f"{f.get('compliance_drop_points', 0.0):+.1f}",
                     f"{f.get('utility_loss_points', 0.0):+.1f}"])
    table(rows)
    body(
        "Table 17 - Five frames compared on DEV attacks, each fixing one diagnosed weakness of "
        "the first. The active ingredient is RECENCY: repeating the constraint AFTER the "
        "untrusted content, so an injection's own 'ignore all previous instructions' does not "
        "get the last word. That alone cuts compliance by about 19 points at no utility cost. "
        "Pronoun depersonalisation and tagged delimiters add security but cost utility, and "
        "v5_routed reuses the shape gate that FAILED as a detector as a router instead -- strong "
        "frame for non-memories, cheap frame for memories -- reaching the same security while "
        "slightly improving utility. Critically, the frame this project first built (v1_prefix, "
        "a prefix-only constraint) is actively HARMFUL: it raises compliance and costs 10 points "
        "of utility, and an earlier reading of it as 'partial' came from a hold-out sample that "
        "flattered it.")
    body(
        "A noise floor belongs with these numbers. Despite temperature 0 and fixed seeds, the raw "
        "baseline read 66, 64 and 61 of 120 across three runs of identical prompts, because "
        "ollama's concurrent batching is not bit-reproducible. Roughly 5 points on n=120 is "
        "therefore the floor: the ~19-point effect is well outside it, and v2, v3 and v5 are NOT "
        "distinguishable from one another. No claim is made that one of the three is best.")
if NV:
    table([["Hold-out 3 (150 sampled attacks, 150 benign)", "Raw", "Neutralised", "Paired test"],
           ["Attack compliance", f"{NV['attack_compliance_raw']['rate']:.1%}",
            f"{NV['attack_compliance_neutralised']['rate']:.1%}",
            f"+{NV['paired_attack_compliance']['only_a']}/-"
            f"{NV['paired_attack_compliance']['only_b']}, "
            f"p={NV['paired_attack_compliance']['p_exact']:.2g}"],
           ["Benign information used", f"{NV['benign_information_used_raw']['rate']:.1%}",
            f"{NV['benign_information_used_neutralised']['rate']:.1%}",
            f"+{NV['paired_benign_utility']['only_a']}/-"
            f"{NV['paired_benign_utility']['only_b']}, "
            f"p={NV['paired_benign_utility']['p_exact']:.2g}"]])
    body(
        "Table 18 - The dev-selected frame, run ONCE on the frozen corpus. Compliance falls 19.3 "
        "points, matching the 20.8 predicted from development data, at p=2.4e-06, while the "
        "change in benign information use is not significant. Since nothing is excluded, this is "
        "a strict improvement on that distribution over any detection-based configuration, all "
        "of which pay 33-55% false positives there. The frame was selected on DEV by a rule "
        "fixed before the comparison ran, and the hold-out was scored once.")

# ------------------------------------------------------------------ ablation
h2("32.47 The Deberta Attribution Was Imprecise: an Ablation")
body(
    "Section 32.27 attributed B14's cross-corpus instability to deberta, on three pieces of "
    "evidence: 90.1% decision agreement on external corpora, per-item catches tracking deberta's "
    "score, and B14 degrading worse across corpora than the component it tracks. That was "
    "reported as a diagnosis and listed as not fixable. A diagnosis naming one feature implies an "
    "experiment, so the fusion was refit on the same training data with that feature removed and "
    "nothing else changed.")
if AB:
    v = AB["variants"]
    rows = [["Variant", "Own attacks", "Hold-out 1", "Hold-out 2", "Gap", "Ordinary benign"]]
    for n, e in v.items():
        rows.append([n, f"{e['own_attacks']['rate']:.1%}",
                     f"{e['holdout1_external_test']['rate']:.1%}",
                     f"{e['holdout2_mosscap']['rate']:.1%}",
                     f"{e['holdout_gap_points']:+.1f}",
                     f"{e['ordinary_benign_fpr']['k']}/{e['ordinary_benign_fpr']['n']}"])
    table(rows)
    body(
        "Table 19 - Removing the feature WIDENS the gap, from +32.9 to +46.6, and costs recall "
        "everywhere, with hold-out 2 collapsing from 59.8% to 40.7%. So deberta is load-bearing "
        "for B14's out-of-distribution recall rather than the source of its instability, the gap "
        "is a property of the fused weights, and the feature cannot be removed to fix it. The "
        "'inherited from deberta' wording was imprecise and is corrected here. It remains "
        "consistent with B18, where adding the same classifier as a HARD RULE gained 18 points "
        "on hold-out 2: a fusion can under-use a feature it contains, which is a different claim "
        "from that feature causing the instability, and the earlier wording conflated the two. "
        "Baseline note: this is a refit at a 0.5% dev-FPR threshold, so its full-feature numbers "
        "differ slightly from published B14; the comparison is internal to the ablation.")

# ------------------------------------------------------------------ calibration
h2("32.48 A Calibration Test: Were the Earlier Prediction Failures a Habit?")
body(
    "Three of the five predictions in the first pre-registration failed and one failed backwards. "
    "That cannot be un-failed, and the useful question is whether the model that produced them "
    "has improved. B17 and B18 had never been scored on hold-out 2, so five predictions with "
    "explicit intervals were committed to `docs/phase17/PREREGISTRATION_2_CALIBRATION.md` before "
    "the measurement, together with the scoring rule: four or five held means calibrated, three "
    "partially, two or fewer means not calibrated and every forward-looking statement in this "
    "document should be read with that attached.")
if CA:
    rows = [["Prediction", "Interval", "Measured", "Outcome"]]
    for k, c in CA["prediction_checks"].items():
        pred = (f"{c['point']:.0%} [{c['lo']:.0%}-{c['hi']:.0%}]" if "point" in c
                else (f">= {c['min_delta']:.0%}" if "min_delta" in c
                      else (f"<= {c['max_k']}" if "max_k" in c else f"<= {c['max_delta']:.0%}")))
        meas = f"{c['measured']:.1%}" if isinstance(c["measured"], float) else str(c["measured"])
        rows.append([c["claim"], pred, meas, "HELD" if c["held"] else "FAILED"])
    table(rows)
    body(
        f"Table 20 - {CA['n_held']}/5 held. {CA['calibration_verdict']} The measurement also "
        f"produces a new best on that hold-out: B18 reaches "
        f"{CA['measured']['B18']['recall']['rate']:.1%} against B14's 54.2%, at "
        f"{CA['measured']['B18']['ordinary_benign_fpr']['k']}/1054 ordinary-benign false "
        f"positives. B17 adds only 0.9 points over B14 there, confirming that on "
        f"injection-shaped text the provenance configuration catches almost nothing the fusion "
        f"does not already catch -- which is why the recommendation in 32.45 separates the two "
        f"threats rather than naming one configuration.")
if ER:
    body(
        f"One further verification belongs with this. The claim that each methodological error in "
        f"this project is prevented by a guard test was an assertion, and an untested guard is "
        f"decoration. `phase17/error_registry.py` reintroduces each error by a concrete source "
        f"mutation and requires its guard to FAIL, then pass again once restored: "
        f"{ER['n_proven']}/{ER['n']} are proven on that standard. Establishing it exposed that "
        f"four of the eight guards had been passing with their error reintroduced, that shell "
        f"scripts were stored with CRLF endings and unrunnable after a Windows checkout, that one "
        f"guard was passing on a file-not-found exit rather than on the behaviour it named, and "
        f"-- twice -- that the mutation harness itself corrupted what it measured. Data artifacts "
        f"are now off limits to mutation for that reason.")

doc.save(P)
print("added 32.46-32.48")
print("DONE")
