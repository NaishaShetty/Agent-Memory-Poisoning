# -*- coding: utf-8 -*-
"""Correct the multi-hop scoping claim in both documents.

The claim was: multi-hop reasoning is outside what this benchmark measures, because the oracle
condition hands the agent perfect evidence and it still answers only 36/60, so the limit is a 7B
agent's reasoning. `multihop_multiagent.py` tested that across six agent families and it is
wrong on both counts.
"""
from __future__ import annotations

import json
from pathlib import Path

import docx

DATA = Path("phase17/data")
M = json.loads((DATA / "multihop_multiagent.json").read_text(encoding="utf-8"))
pa = M["per_agent"]

rows = [["Agent", "LLM judge", "NLI entailment", "Strict (judge AND NLI)"]]
for a, v in pa.items():
    rows.append([a, "%.1f%%" % (100 * v["judge"]["rate"]),
                 "%.1f%%" % (100 * v["nli"]["rate"]),
                 "%.1f%%" % (100 * v["strict_judge_and_nli"]["rate"])])

NEW_TEXT = [
    "CORRECTION (round 6). The claim that multi-hop reasoning lies outside what this benchmark "
    "measures rested on the oracle condition reaching only 36/60 with perfect evidence supplied, "
    "attributed to a 7B agent's reasoning limit. `multihop_multiagent.py` re-ran that condition "
    "across six agent families on the identical cases, prompt and scoring, and the attribution "
    "is wrong on both counts.",
    "It is not model capability. Gemini 3.5 Flash Lite, a far more capable hosted model, scores "
    f"{100 * pa['gemini (gemini-3.5-flash-lite)']['strict_judge_and_nli']['rate']:.1f}% -- inside "
    f"the local band and BELOW both llama3.1:8b "
    f"({100 * pa['llama3.1:8b']['strict_judge_and_nli']['rate']:.1f}%) and phi3:mini "
    f"({100 * pa['phi3:mini']['strict_judge_and_nli']['rate']:.1f}%), a 3.8B model. The six "
    f"families span {M['analysis']['local_spread_points']} points with no relationship to size, "
    "which is not the signature of a capability ceiling.",
    "And it is mostly an EVALUATOR artifact. Separating the two components of the strict scoring "
    "ensemble shows every agent answering 80-87% of multi-hop questions correctly under the LLM "
    "judge, while the NLI entailment-equivalence check rejects roughly one correct answer in "
    "three -- a correct free-form answer is frequently not bidirectionally entailed with a "
    "differently-phrased gold string. The oracle 'ceiling' is therefore largely the strictness "
    "of the ensemble, not a failure of reasoning.",
    "This is the phenomenon this project's own Section 12.13 and research question RQ3 identify: "
    "deterministic and strict semantic metrics systematically under-estimate genuine correctness. "
    "Multi-hop was scoped out on the strength of a number this methodology already predicted "
    "would be depressed. The correct statement is narrower and more useful: the multi-hop oracle "
    "figure is a strict-ensemble lower bound, agents reach roughly 83% under the judge metric, "
    "and any defended multi-hop figure must be read under both metrics rather than the strict "
    "one alone.",
]

CAPTION = ("Multi-hop ORACLE condition by agent family, identical cases and prompt. The judge "
           "column is the same LLM-judge metric this project uses as metric 8; the strict column "
           "is the judge-AND-NLI ensemble the earlier figure was computed with. Source: "
           "phase17/data/multihop_multiagent.json.")

# ------------------------------------------------------------------ 1. methodology
P = "Methodology Draft.docx"
doc = docx.Document(P)
MARK = "32.34 The Multi-Hop Ceiling Is an Evaluator Artifact, Not a Reasoning Limit"
if not any(MARK in p.text for p in doc.paragraphs):
    concl = next(p for p in doc.paragraphs if p.text.startswith("33. Overall Conclusion"))
    BODY = doc.paragraphs[4].style
    h = concl.insert_paragraph_before(MARK)
    h.style = doc.styles["Heading 2"]
    for t in NEW_TEXT:
        q = concl.insert_paragraph_before(t)
        q.style = BODY
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
    cap = concl.insert_paragraph_before("Table 5 - " + CAPTION)
    cap.style = BODY
    doc.save(P)
    print("methodology: added 32.34")
else:
    print("methodology: already corrected")

# ------------------------------------------------------------------ 2. results builder
rb = Path("phase17/build_results_analysis_docx.py")
s = rb.read_text(encoding="utf-8")
OLD = ('P("Agent capability is a floor on every harm number. All agent-side measurement uses a 7B model. "\n'
       '  "The multi-hop condition is the clearest case: the oracle arm hands the agent perfect evidence "\n'
       '  "and it still answers only 36/60 correctly, so a defense can be neither credited nor blamed for "\n'
       '  "the 24 it fails with perfect evidence. Multi-hop reasoning is therefore declared outside what "\n'
       '  "this benchmark measures and no claim here rests on it. The same ceiling bounds every harm rate "\n'
       '  "less visibly.")')
NEW = ('P("Agent capability bounds every harm number, since all agent-side measurement uses a 7B model. "\n'
       '  "But the multi-hop case, which this project previously used as the clearest illustration of that '
       'bound, turned out not to illustrate it at all -- see Section 10A.")\n'
       'H("10A. A Correction: the Multi-Hop Ceiling Was an Evaluator Artifact", 1)\n'
       'for _t in MULTIHOP_CORRECTION:\n'
       '    P(_t)\n'
       'if MHA:\n'
       '    _rows = [["Agent", "LLM judge", "NLI entailment", "Strict (judge AND NLI)"]]\n'
       '    for _a, _v in MHA["per_agent"].items():\n'
       '        _rows.append([_a, pct(_v["judge"]["rate"]), pct(_v["nli"]["rate"]),\n'
       '                      pct(_v["strict_judge_and_nli"]["rate"])])\n'
       '    TBL(_rows)\n'
       '    CAP("Table 10A. " + MULTIHOP_CAPTION)')
if OLD in s:
    s = s.replace(OLD, NEW, 1)
    s = s.replace('FAM = L("family_breakdown.json")',
                  'FAM = L("family_breakdown.json")\nMHA = L("multihop_multiagent.json")\n'
                  f'MULTIHOP_CORRECTION = {NEW_TEXT!r}\n'
                  f'MULTIHOP_CAPTION = {CAPTION!r}')
    rb.write_text(s, encoding="utf-8")
    print("results builder: multi-hop claim corrected")
else:
    print("results builder: anchor not found (already corrected?)")
print("DONE")
