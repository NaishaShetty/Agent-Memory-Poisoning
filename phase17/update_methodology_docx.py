"""One-shot script: updates 'Methodology Draft.docx' in place to cover Phases 14-17
(the doc previously stopped at Phase 13), correct the now-stale title/abstract/RQs, and
add three new data-grounded figures. A backup was taken separately before running this.

Insertion strategy: python-docx appends new paragraphs/tables/pictures at the END of the
document body. To place new content BEFORE the existing "Appendix A" section (so Phases
14-17 read in narrative order, before the prompt appendix), every new paragraph/table/
picture is created normally (which appends it at the end) and then its underlying oxml
element is relocated with `anchor._p.addprevious(new_element)` -- repeated calls in
forward reading order build up the correct sequence immediately before the anchor.
"""
from __future__ import annotations

import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

PATH = "Methodology Draft.docx"
FIGDIR = "phase17/data/methodology_figs"

doc = docx.Document(PATH)

# ---------------------------------------------------------------------------
# 1. Fix the now-stale title/subtitle and Abstract/RQ/Contributions section.
# ---------------------------------------------------------------------------
subtitle_para = doc.paragraphs[1]
if subtitle_para.runs:
    subtitle_para.runs[0].text = (
        "Phases 1-17: Dataset Foundations, Benchmark Infrastructure, the Clean Memory-Augmented Agent, the Unified "
        "Memory Manipulation Attack Benchmark, Instrumentation, Monitoring & Attribution, Governance Defense, "
        "Propagation Monitoring, Sleeper Detection, Attack-Origin Attribution, Adaptive Risk-Based Hardening, "
        "Learned (GNN/GLN) Components, Security & Attribution Metrics Evaluation, Systems/Scalability Evaluation, "
        "Integrated Security Evaluation, Final Validation, and Ablation & Generalization"
    )
    for extra_run in subtitle_para.runs[1:]:
        extra_run.text = ""

# Abstract update paragraph, inserted right after the existing Abstract text (paragraph 3).
abstract_para = doc.paragraphs[3]
upd = abstract_para.insert_paragraph_before(
    "Update (2026-09-27, Phase 17 completion). Phases 14-17, added after this Abstract was first written, extend "
    "the project from a clean-agent/attack-benchmark study into a full governance-defense evaluation and "
    "generalization study: a governance defense stack (admission, retrieval-consensus, propagation-containment, "
    "sleeper detection, adaptive risk-based composition, and two generalization-focused live configurations, B11 "
    "and B12) is evaluated for detection, false-positive rate, and utility cost across unseen attack mechanisms, an "
    "unseen language (Chinese), two real memory foundations (A-mem-sys and Mem0, both exercised live for the first "
    "time in this project's history), and adversarial defense-aware paraphrase and provenance-forgery attempts. The "
    "central, honestly-reported finding is that mechanism-level, judge-plus-embedding detection generalizes "
    "substantially better than the original family-tuned signal set (unseen-mechanism exclusion rises from 0/60 to "
    "35/60 across three rounds of fixes), while defense-aware paraphrase of non-contradictory claims and additive "
    "fabrications remain open problems that content-only analysis cannot close without real provenance/timestamp "
    "evidence. See Sections 29-33.",
)
upd.style = abstract_para.style

# New RQ5, inserted after RQ4 (paragraph index of "RQ4." text) and before "This paper's contributions are:".
rq4_para = next(p for p in doc.paragraphs if p.text.startswith("RQ4."))
contrib_intro = next(p for p in doc.paragraphs if p.text.strip() == "This paper's contributions are:")
rq5 = contrib_intro.insert_paragraph_before(
    "RQ5. Once a governance defense stack is built and tuned against seven reconstructed attack families, does it "
    "detect the underlying manipulation BEHAVIOR those families share, or merely the SURFACE characteristics of the "
    "specific artifacts it was tuned against -- tested against unseen attack mechanisms, an unseen language, unseen "
    "memory foundations, and defense-aware adversarial paraphrase and provenance forgery? (Addressed in Section 33, "
    "Phase 17.)"
)
rq5.style = rq4_para.style

new_contrib = contrib_intro.insert_paragraph_before(
    "A governance defense stack (admission, retrieval-consensus, propagation-containment, sleeper detection, "
    "adaptive risk-based composition, and learned components) evaluated end-to-end for detection, false-positive "
    "rate, and utility cost (Phases 6-15), followed by an ablation and generalization phase (Phase 17) that "
    "measures -- rather than assumes -- how much of that detection is family-specific tuning versus genuine "
    "mechanism-level generalization, closing five separate rounds of disclosed negative findings with root-caused "
    "fixes and a small number of honestly-reported, still-open negative results."
)
new_contrib.style = abstract_para.style

doc.save(PATH)
print("Stage 1 (title/abstract/RQ/contrib) done.")
