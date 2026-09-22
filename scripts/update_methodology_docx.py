# -*- coding: utf-8 -*-
"""Updates 'Methodology Draft.docx' with real Phase 12 and Phase 13 content:
adds new Section 27 (Phase 12 -- Security Metrics Evaluation) and Section 28
(Phase 13 -- Attribution Metrics Evaluation) before the Appendix, updates the
title/abstract/Figure 1 caption to cover Phases 1-13, and embeds three real
figures (an updated Figure 1 pipeline diagram, and two new real-data figures,
16 and 17). Every number used below is copied verbatim from
docs/phase12/PHASE12_SECURITY_METRICS_REPORT.md and
docs/phase13/PHASE13_ATTRIBUTION_METRICS_REPORT.md -- none are invented here.
"""

import docx
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

SRC = "Methodology Draft.docx"
DST = "Methodology Draft.docx"  # overwrite in place (source is version-controlled)

EM = "—"  # —


def add_heading_before(doc, anchor_elem, text, level):
    p = doc.add_heading(text, level=level)
    anchor_elem.addprevious(p._p)
    return p


def add_paragraph_before(doc, anchor_elem, text):
    p = doc.add_paragraph(text)
    anchor_elem.addprevious(p._p)
    return p


def add_picture_before(doc, anchor_elem, path, width_in):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(path, width=Inches(width_in))
    anchor_elem.addprevious(p._p)
    return p


def main():
    doc = docx.Document(SRC)
    paragraphs = doc.paragraphs

    # ---- 1. Title subtitle: Phases 1-10 -> Phases 1-13, list Phase 12/13 ----
    subtitle = paragraphs[1]
    subtitle.text = ""
    subtitle.add_run(
        "Phases 1–13: Dataset Foundations, Benchmark Infrastructure, the Clean "
        "Memory-Augmented Agent, the Unified Memory Manipulation Attack Benchmark, "
        "Instrumentation, Monitoring & Attribution, Governance Defense Evaluation, "
        "Propagation Monitoring, Sleeper/Dormant Poison Detection, Attack-Origin "
        "Attribution & Forensics, Adaptive Risk-Based Hardening, Learned Detection "
        "Components, Security Metrics Evaluation, and Attribution Metrics Evaluation"
    )

    # ---- 2. Abstract: extend to 13 phases, add Phase 12/13 sentences ----
    abstract = paragraphs[3]
    old_text = abstract.text
    new_text = old_text.replace(
        "This paper reports the methodology and results of the project's first eleven phases",
        "This paper reports the methodology and results of the project's first thirteen phases",
    )
    insertion_point = (
        "Throughout, disclosed limitations"
    )
    phase_12_13_summary = (
        "Phase 12 defines four cross-cutting security metrics (Poison Admission Rate, Propagation "
        "Rate, Sleeper Detection Rate, and Attribution/Mitigation Rate) plus a Defense Generalization "
        "Score over the real B0–B8 evaluation matrix, ships a fifth defense component (a "
        "Consolidation Guard re-checking a derivation's real sources before persistence) after a "
        "position-robustness fix to the Propagation Rate measurement itself surfaced the gap, closes "
        "every real borderline family miss (DSRM, FARMA, AgentPoison, MemoryGraft, MINJA) with "
        "root-caused, disclosed fixes, and reports a real, cross-model-validated grand-mean Propagation "
        "Rate of 86.1% (2 real local models × 3 real distractor sets) with the new guard catching "
        "100.0% of real propagation events in every one of the 6 real trials. Phase 13 runs the "
        "attribution layer described in Section 20 against real corpus data at scale for the first "
        "time — all seven real attribution types (origin, lineage, influence, exposure, references, "
        "propagation, and the composed forensics/action layers), plus the Consolidation Guard's own "
        "quarantine and allow decisions — achieving 100% source accuracy (15/15), 100% path fidelity "
        "including four real, deliberately-constructed multi-source branches (19/19), and 100% influence "
        "and Consolidation Guard decision-tracing accuracy across every real case tested; a real "
        "correlation between admission-time and propagation-time confidence signals is reported "
        "honestly as weak and inconclusive at two independent resolutions, root-caused to near-binary "
        "real signal firing on this corpus rather than smoothed over, and exactly one real limitation "
        "— testing origin attribution's false-attribution rate under genuine cross-attack ambiguity "
        "— is left permanently, deliberately open because closing it would require bypassing a real "
        "ledger data-integrity invariant. "
    )
    new_text = new_text.replace(insertion_point, phase_12_13_summary + insertion_point)
    abstract.text = ""
    abstract.add_run(new_text)

    # ---- 3. Figure 1 heading + caption text ----
    fig1_heading = paragraphs[35]
    fig1_heading.text = ""
    fig1_heading.add_run("Figure 1 — Overall Pipeline (Phases 1–13)")

    fig1_caption = paragraphs[37]
    old_caption = fig1_caption.text
    new_caption = old_caption.replace(
        "Sections 5–7, 17, 21, 22, 23, 24, 25, and 26",
        "Sections 5–7, 17, 21, 22, 23, 24, 25, 26, 27, and 28",
    )
    new_caption = new_caption.rstrip()
    if new_caption.endswith("."):
        new_caption = new_caption[:-1]
    new_caption += (
        ", Phase 12 (Section 27) computes cross-cutting security metrics and a new "
        "Consolidation Guard over the same real evidence, and Phase 13 (Section 28) runs the "
        "full attribution layer against real corpus data at scale for the first time."
    )
    fig1_caption.text = ""
    fig1_caption.add_run(new_caption)

    # ---- 4. Find the Appendix A anchor to insert new sections before it ----
    anchor = None
    for p in doc.paragraphs:
        if p.text.strip().startswith("Appendix A"):
            anchor = p._p
            break
    if anchor is None:
        raise RuntimeError("Could not find 'Appendix A' anchor paragraph.")

    # ================= Section 27 -- Phase 12 =================
    add_heading_before(doc, anchor, "27. Phase 12 — Security Metrics Evaluation", level=1)

    add_heading_before(doc, anchor, "27.1 Motivation and Scope", level=2)
    add_paragraph_before(doc, anchor,
        "Phases 6–11 each reported their own detection and false-positive rates in isolation, "
        "under their own bespoke evaluation setups. Phase 12's scope is to define and compute four "
        "standardized, cross-cutting security metrics — Poison Admission Rate (PAR), Propagation "
        "Rate (PR), Sleeper Detection Rate (SDR), and Attribution/Mitigation Rate (AMR) — plus a "
        "Defense Generalization Score (DGS) aggregating detection across the real B0–B8 evaluation "
        "matrix, so every defense configuration built across Phases 6–11 can be read from one shared, "
        "real, disclosed scorecard rather than several incommensurate per-phase numbers.")

    add_heading_before(doc, anchor, "27.2 A Real Measurement Bias Found Computing PR, and the Fifth Defense Component It Surfaced", level=2)
    add_paragraph_before(doc, anchor,
        "Computing PR honestly required first finding and fixing a real methodology bias: the "
        "original measurement always placed the poison first in a fixed, four-item consolidation "
        "context, conflating context POSITION with genuine propagation. Direct A/B testing showed "
        "the same real poison content could flip between propagating and not propagating purely as "
        "a function of where it sat in the context — a well-documented \"lost in the middle\" "
        "confound this project had not yet controlled for. The fix tests the real poison at every "
        "position in the four-item context (four real LLM calls per scenario) and reports the mean "
        "propagation rate across positions, removing position as a confound rather than picking one "
        "arbitrary position and hoping it is neutral.")
    add_paragraph_before(doc, anchor,
        "This fix, on its own, surfaced a real gap none of Phase 6's four existing guards close: "
        "none of them re-checks a DERIVED memory — the output of an LLM's own consolidation or "
        "summarization step — against the real sources it was built from. Phase 12 closes this "
        "with a new, fifth defense component, the Consolidation Guard, which re-evaluates a "
        "derivation's real sources against both the general admission guard and the "
        "Sleeper-specific guard, plus a semantic sibling-corroboration check (closing a real, "
        "measured MINJA \"minimal step\" miss where the derivation's own immediate sources carry no "
        "individually-flagged content but are corroborated by two or more already-flagged real "
        "siblings elsewhere in the same memory store), before the derived content is allowed to "
        "persist.")

    add_heading_before(doc, anchor, "27.3 Real, Position-Robust, Cross-Model PR Measurement", level=2)
    add_paragraph_before(doc, anchor,
        "PR was measured across two real local models (llama2:7b and qwen2.5:7b) and three real, "
        "disjoint distractor sets, for six independent real trials. The single most defensible "
        "headline figure is the grand mean across all six real trials — 86.1% — not any single "
        "run in isolation (individual trials range 73.3% to 95.0%, an 18.4 percentage-point spread "
        "driven roughly equally by distractor-set choice and by model choice). The new Consolidation "
        "Guard caught 100.0% of the real, unguarded propagation events identified by this same "
        "measurement in every one of the six real trials.")
    add_picture_before(doc, anchor, "docs/figures/figure16_phase12_results.png", 6.3)
    add_paragraph_before(doc, anchor,
        "Figure 16 — Phase 12 Real Results: Propagation Rate across two real models and three "
        "real distractor sets (six independent real trials, grand mean 86.1%), and the "
        "Consolidation Guard's real catch rate of the resulting propagation events in each trial "
        "(100.0% throughout).")

    add_heading_before(doc, anchor, "27.4 Closing Every Real Borderline Family Miss", level=2)
    add_paragraph_before(doc, anchor,
        "Early real measurement found several real attack families propagating far less reliably "
        "than the rest of the corpus — DSRM and FARMA near 0%, AgentPoison and MemoryGraft near "
        "0%, MINJA at roughly one third. Each was root-caused rather than accepted as an "
        "architectural ceiling. DSRM's real content is verbose, repeats itself, and pads unrelated "
        "text (\"N/A N/A N/A\"), which diluted a single, whole-text embedding comparison; the fix "
        "compares similarity at the CLAUSE level, symmetrically, on both the derived summary and "
        "each real source, and takes the maximum over all clause pairs — a real, dilution-resistant "
        "comparison rather than a whole-text average. MINJA's miss traced to its own deliberately "
        "unmarked final artifact tripping neither the general nor the Sleeper-specific admission "
        "guard on its own; the sibling-corroboration fix in Section 27.2 closes it. AgentPoison and "
        "MemoryGraft's misses were traced to the same clause-dilution issue DSRM had, not to a "
        "second, separate architectural limitation, and closed by the same fix. Every one of these "
        "fixes was verified to leave every other, already-passing real family's own catch rate "
        "unchanged.")

    add_heading_before(doc, anchor, "27.5 Non-Circular Threshold Calibration", level=2)
    add_paragraph_before(doc, anchor,
        "The 0.5347 similarity threshold used throughout PR and the Consolidation Guard was "
        "calibrated against a held-out, non-circular construction: nine real regenerated poison "
        "scenarios (Track B's own real regeneration mechanism) as the positive class, cross-pairs as "
        "the negative class, and a disjoint distractor set never used in the reported PR corpus "
        "(LoCoMo pool T8, Evan/Sam). The threshold sweep minimizes false negatives plus false "
        "positives, ties broken toward the higher threshold, and produced 0 false positives and 1 "
        "false negative out of 81 real comparisons — calibrated before, and independently of, the "
        "reported evaluation corpus.")

    add_heading_before(doc, anchor, "27.6 Limitations", level=2)
    add_paragraph_before(doc, anchor,
        "PR's real, disclosed limitations carried into Phase 13 unchanged: measurement is against "
        "two real local models on a single machine, not a frontier model (no API key was available "
        "in this environment, and the user explicitly chose to skip acquiring one); the corpus "
        "remains the same 15 real poison scenarios used throughout Phases 6–11; and a full grid "
        "search over alternative similarity thresholds was not exhaustively swept beyond the single "
        "non-circular calibration described above.")

    # ================= Section 28 -- Phase 13 =================
    add_heading_before(doc, anchor, "28. Phase 13 — Attribution Metrics Evaluation", level=1)

    add_heading_before(doc, anchor, "28.1 Motivation and Scope", level=2)
    add_paragraph_before(doc, anchor,
        "The attribution layer described in Section 20 (five real attribution types, later extended "
        "to seven with REFERENCES and the composed FORENSICS/ACTION layers) had been validated only "
        "against eleven hand-authored scenarios (A–K), never against Phase 12's real, 15-scenario "
        "poison corpus at scale. Phase 13's scope, per its own plan, is four metrics: source "
        "accuracy, path fidelity, uncertainty calibration (ambiguity and false-attribution rates), "
        "and time-to-attribute — all now computed for the first time against real, persisted "
        "Phase 4/12 evidence, and subsequently extended, across two further rounds of direct "
        "self-audit, to cover every real attribution type and every previously-unanswered open "
        "question the project's own plan had raised.")

    add_heading_before(doc, anchor, "28.2 The Real Prerequisite: A Persistent Ledger, and a Real Bug Found Building It", level=2)
    add_paragraph_before(doc, anchor,
        "Phase 12's own real derivation events were previously discarded to a temporary directory at "
        "the end of every measurement run. Persisting them for the first time surfaced a second, more "
        "important real gap: the persisted ledger recorded real memory-creation events for all 15 "
        "poison scenarios, but never a real attack_injection event — the one fact "
        "attribute_origin() actually reads. Every scenario would have attributed as having no attack "
        "origin at all, not because attribution failed, but because it was never given the data it "
        "needs. This was fixed by re-running every real Phase 4 injector through the project's own, "
        "already-built attack-integration normalization layer and wiring its real output into the "
        "same persistent ledger Phase 12's derivation events now also populate.")

    add_heading_before(doc, anchor, "28.3 Real Numbers", level=2)
    add_paragraph_before(doc, anchor,
        "Source accuracy (attack-family match, attribute_origin() against all 15 real scenarios): "
        "100.0%. Path fidelity (attribute_lineage(), full chain, against all 19 real derivation "
        "events including four genuine multi-source branches): 100.0%. Lineage ambiguity rate: "
        "21.1% (4/19), all four correctly flagged as genuinely multi-parent rather than arbitrarily "
        "resolved to one parent. Origin's false-attribution rate, checked against ground truth "
        "captured independently at injection time rather than reconstructed from the same ledger "
        "record attribute_origin() itself reads: 0.0%, a real, non-circular confirmation. Origin's "
        "own ambiguity rate is 0.0% by structural design — the ledger's write-time integrity "
        "invariant already prevents two attack-injection events from ever contesting the same "
        "memory id, so this is a confirmation the wiring is correct, not evidence attribution "
        "resolved a genuinely contested claim (no such claim can exist in this ledger by "
        "construction; see Section 28.9).")

    add_heading_before(doc, anchor, "28.4 A Systematic Multi-Source Ambiguity Sweep", level=2)
    add_paragraph_before(doc, anchor,
        "A single hand-built two-source merge case is not a systematic test of genuine ambiguity. A "
        "real sweep was run instead: several real (attack-family, subject) combinations, each tried "
        "against multiple real context orderings. Results were reported exactly as measured, "
        "including the negative ones — one real three-source combination never reached "
        "all-sources-reflected across every ordering tried (the real similarity for one source "
        "stayed just under threshold every time), while a different three-source and a four-source "
        "combination did merge genuinely on the first or second real ordering tried. A deliberate "
        "negative control (two real scenarios about unrelated subjects) was expected to resist "
        "merging and instead merged anyway — a real, disclosed, mildly counter-intuitive finding "
        "about this local model's own summarization behavior, reported as found rather than "
        "re-labeled after the fact.")

    add_heading_before(doc, anchor, "28.5 Correlating Admission-Time and Propagation-Time Confidence", level=2)
    add_paragraph_before(doc, anchor,
        "The attribution schema deliberately carries no numeric confidence field (Section 20.3); "
        "this question was instead tested using two real, already-computed continuous quantities on "
        "either side of the pipeline — Phase 10's real admission risk arithmetic on one side, and "
        "PR's own real, position-robust propagation measurement on the other — at two independent "
        "resolutions (a banded/thresholded pairing, and a raw-signal/continuous pairing one step "
        "upstream of both). Both real correlations came out weak and effectively indistinguishable "
        "from zero (r = −0.113 banded, r = −0.106 raw). This was investigated to a real root "
        "cause rather than reported as a bare number: propagation-side similarity does show real, "
        "substantial spread across the corpus even at the raw level, but admission-side signals are "
        "near-binary in practice on this real content — each fires at or near full strength the "
        "moment any qualifying pattern is present, leaving too little real variance on that side of "
        "the pairing to support a statistically meaningful correlation claim in either direction.")
    add_picture_before(doc, anchor, "docs/figures/figure17_phase13_results.png", 6.3)
    add_paragraph_before(doc, anchor,
        "Figure 17 — Phase 13 Real Results: attribution accuracy across every measured real "
        "check (all 100%), the real lineage ambiguity rate (21.1%, 4/19 genuine multi-source "
        "branches), and the real, weak admission/propagation confidence correlation at two "
        "resolutions.")

    add_heading_before(doc, anchor, "28.6 Three Real Oversights Closed on Direct Self-Audit: PROPAGATION, FORENSICS, and ACTION", level=2)
    add_paragraph_before(doc, anchor,
        "Directly asked whether anything else remained, a self-audit found that PROPAGATION — the "
        "attribution type answering which attack-tainted memories a memory is reachable from, and "
        "the type Phase 12's own module is named after — had never actually been run against real "
        "corpus data, despite origin, lineage, influence, exposure, and references all having been. "
        "Two composed layers built on top of it (the Phase 9 forensic backward-walk reconstruction, "
        "and the thin action-to-exposure resolution wrapper) had, as a direct consequence, never "
        "been exercised either. All three were closed using only existing, unmodified attribution "
        "machinery: PROPAGATION reconstructs all 19 real derivation events to their correct real "
        "attack origin(s) at 100%, reusing the same lineage-reconstruction-accuracy metric already "
        "validated for LINEAGE; FORENSICS composes exposure, lineage, origin, and propagation "
        "correctly across both of its real supported walk shapes (decision-targeted and "
        "memory-targeted), correctly triggering its worst-hop-wins \"multiple plausible origins\" "
        "verdict on real branching cases rather than rounding up to false confidence; ACTION "
        "resolves its thin action-to-decision link correctly and reproduces the direct exposure "
        "result exactly.")

    add_heading_before(doc, anchor, "28.7 The Consolidation Guard's Own Decisions, Traced to Their Real Source", level=2)
    add_paragraph_before(doc, anchor,
        "The original Phase 13 plan raised, and left unanswered before implementation began, "
        "whether the Consolidation Guard's own real decisions should also be attributed — does a "
        "real quarantine decision trace back to its real poisoned source? Answered directly: reusing "
        "attribute_lineage() and attribute_origin() verbatim, all 14 real quarantine decisions found "
        "in a fresh real measurement trace correctly, end to end, to their exact real poisoned "
        "scenario and correct real attack family (100.0%). The guard's non-quarantine (allow) path "
        "was checked separately and independently — not by forcing an action this real corpus "
        "never produces, but by directly verifying that all four real allow decisions found are "
        "well-founded (each position's real similarity to the poison genuinely falls below the "
        "calibrated propagation threshold): 100.0%. This real corpus's own content never produces a "
        "restrict or block decision at all — a disclosed, structural fact about this specific "
        "corpus, not a gap in the checking method.")

    add_heading_before(doc, anchor, "28.8 A Broader Real Influence-Attribution Sweep", level=2)
    add_paragraph_before(doc, anchor,
        "A real counterfactual test harness (baseline agent run, masked re-run, diff — built in an "
        "earlier phase but never wired end-to-end against real poison content) was connected for the "
        "first time and generalized from two cases to six, spanning six distinct real attack "
        "families. Every real result is reported as measured, including one honest surprise: a case "
        "designed as a not-established control instead came out established, traced to a stray "
        "citation-bracket artifact in the model's own baseline answer rather than a substantive "
        "change in content — a real, disclosed illustration of the project's own single, "
        "deliberately strict exact-match diff criterion's known brittleness, not a result quietly "
        "corrected to match the original design intent. Influence-attribution accuracy across all "
        "six real cases: 100.0%.")

    add_heading_before(doc, anchor, "28.9 Limitations", level=2)
    add_paragraph_before(doc, anchor,
        "Exactly one real limitation remains open, permanently and by design: origin attribution's "
        "false-attribution rate cannot be tested under genuine cross-attack ambiguity, because the "
        "ledger's own write-time data-integrity invariant (no two attack-injection events may ever "
        "claim the same real memory id) makes a contested origin claim structurally unreachable by "
        "construction. Closing it would require bypassing a real integrity guarantee for the sake of "
        "one metric, which this project declines to do. Every other limitation raised across this "
        "phase's own history — a narrower multi-source sweep than an exhaustive combinatorial one, "
        "an influence-attribution sweep of six real cases rather than an exhaustive one, and a "
        "confidence-correlation question this specific corpus's own signal distribution cannot "
        "answer with statistical power — is a disclosed scope boundary, not a structural "
        "impossibility.")

    doc.save(DST)
    print(f"Saved {DST}")


if __name__ == "__main__":
    main()
