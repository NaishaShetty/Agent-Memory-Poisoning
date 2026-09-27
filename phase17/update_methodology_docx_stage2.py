# -*- coding: utf-8 -*-
"""Stage 2: insert Sections 29-33 (Phases 14-17 + overall conclusion) before Appendix A,
plus three new data-grounded figures and two tables."""
import docx
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

PATH = "Methodology Draft.docx"
FIGDIR = "phase17/data/methodology_figs"

doc = docx.Document(PATH)
anchor = next(p for p in doc.paragraphs if p.text.startswith("Appendix A"))

BODY_STYLE = doc.paragraphs[4].style  # the Abstract body paragraph's style (a normal body style)


def h1(text):
    p = anchor.insert_paragraph_before(text)
    p.style = doc.styles["Heading 1"]
    return p


def h2(text):
    p = anchor.insert_paragraph_before(text)
    p.style = doc.styles["Heading 2"]
    return p


def h3(text):
    p = anchor.insert_paragraph_before(text)
    p.style = doc.styles["Heading 3"]
    return p


def body(text):
    p = anchor.insert_paragraph_before(text)
    p.style = BODY_STYLE
    return p


def picture(path, caption, width_in=5.5):
    # add_picture appends at the very end of the document body; relocate it immediately
    # before `anchor` so the figure lands in narrative order.
    pic_para = doc.add_picture(path, width=Inches(width_in))
    pic_paragraph = doc.paragraphs[-1]
    pic_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    anchor._p.addprevious(pic_paragraph._p)
    cap = anchor.insert_paragraph_before(caption)
    cap.style = doc.styles["Caption"] if "Caption" in [s.name for s in doc.styles] else BODY_STYLE
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return pic_paragraph


def table(headers, rows, caption=None):
    if caption:
        cap = anchor.insert_paragraph_before(caption)
        cap.style = BODY_STYLE
        cap.runs[0].bold = True if cap.runs else None
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    try:
        t.style = "Table Grid"
    except KeyError:
        pass  # template has no "Table Grid" style; leave default (still a real, readable table)
    for j, hdr in enumerate(headers):
        cell = t.rows[0].cells[j]
        cell.text = hdr
        for r in cell.paragraphs[0].runs:
            r.bold = True
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            t.rows[i + 1].cells[j].text = str(val)
    anchor._p.addprevious(t._tbl)
    spacer = anchor.insert_paragraph_before("")
    spacer.style = BODY_STYLE
    return t


# ===========================================================================
# 29. Phase 14 - Scalability / Systems Evaluation
# ===========================================================================
h1("29. Phase 14 - Scalability / Systems Evaluation")
body(
    "Phase 14 measures the live, per-task cost and utility impact of the governance defense stack (Section 21) "
    "against real workloads, closing Phase 6-13's own disclosed \"no live utility numbers exist\" gap. "
    "`phase14/defended_retrieval.py::REAL_CONFIGS` names every live defense configuration (B0 through B10 at this "
    "phase; B11/B12 are Phase 17 additions, Section 32). Two real tracks are run: Track A (benign question-answering "
    "utility, real LoCoMo and LongMemEval cases) and Track B (real poison-case exclusion and forged-answer rate, the "
    "9 real Phase 6-11 poison scenarios). A real bug fix mid-phase (`reuse_if_context_unchanged`) found that "
    "re-generating an LLM answer for a context the defense did not actually change measured only local-model "
    "sampling noise, not a real defense cost -- fixed by reusing the B0 baseline result whenever a config's kept "
    "context is byte-identical to it."
)
body(
    "B3, B5, B6, and B7 are proven degenerate (byte-identical to B0, B2, B1, and B4 respectively) in this live path "
    "because no real Phase 14 task carries real ancestor memories, so `UTILITY_PILOT_CONFIGS` restricts the live "
    "campaign to the 7 genuinely distinct configurations (B0, B1, B2, B4, B8, B9, B10), with the degenerate four "
    "reported by proven equivalence rather than re-run. B9's live rule is `GROUPED_GATED_ADMISSION_CORROBORATED`, a "
    "separate, additive composition rule from the offline B9 matrix's `GROUPED_GATED` (Section 25.4) -- shipping it "
    "as a new rule, rather than editing `GROUPED_GATED` itself, was verified to leave every frozen Phase 6-12 number "
    "byte-identical (full cross-phase regression after the change)."
)
body(
    "Real Phase 14 result: on n=150+150 real cases, B9's live rule reaches URS=1.0 (task success identical to B0) "
    "while excluding 9/9 real poison cases and reducing the forged-answer rate from 3/9 (B0) to 0/9. B10 (the "
    "learned GNN/GLN blend with an untrained z-score corroboration gate) reaches URS=1.016 with the same 9/9 "
    "exclusion. Limitations disclosed at this phase: the live model is not perfectly deterministic (repeated B0 "
    "runs vary by 1-2 tasks), and Track A/B utility depends on the same local Ollama models used everywhere else in "
    "this project."
)

# ===========================================================================
# 30. Phase 15 - Integrated Security Evaluation
# ===========================================================================
h1("30. Phase 15 - Integrated Security Evaluation")
body(
    "Phase 15 assembles a cross-cutting matrix across every defense configuration and every real corpus this "
    "project has built (the frozen 75-scenario corpus, the Phase 14 live cases, and per-dataset benign pools), and "
    "closes five follow-up findings surfaced by Phase 14's own utility run: a real LongMemEval false-positive rate, "
    "a real 0%-vs-100% Sleeper-detection gap between two evaluation paths, a B10 calibration-transfer failure "
    "across datasets, a B10 seed/tie-handling issue, and a wording correction distinguishing \"flagged\" "
    "(action != ALLOW) from \"excluded\" (QUARANTINE/BLOCK) consistently across every report this project produces "
    "from this point forward -- a distinction Section 32 (Phase 17) treats as load-bearing throughout."
)
body(
    "B10's own per-dataset decomposition (`phase15/b10_per_dataset.py`) introduces a held-out calibration protocol "
    "(`calibration=\"per_dataset_heldout\"`) and a corroboration gate requiring agreement between the learned score "
    "and an independent z-score detector before any exclusion -- closing a real, disclosed in-sample-FPR "
    "overstatement the un-gated version exhibited. Every Phase 15 number that later feeds Phase 16/17 is reported "
    "with this gate on by default."
)

# ===========================================================================
# 31. Phase 16 - Final Evaluation / Validation
# ===========================================================================
h1("31. Phase 16 - Final Evaluation / Validation")
body(
    "Phase 16 synthesizes Phases 1-15's own numbers into a single final-validation report "
    "(`docs/phase16/PHASE16_SYNTHESIS_REPORT.md`), the traditional end-of-project deliverable this methodology "
    "would have stopped at before Phase 17 was scoped. A qualification note was added to this report after Phase 17 "
    "disclosed that several of Phase 16's \"resolved\" findings held only in-sample (tuned and measured on the "
    "same corpus) and needed a genuinely held-out re-test -- recorded as a dated addendum to the original report, "
    "per this project's own \"never silently rewrite a historical result\" discipline (Section 10)."
)

# ===========================================================================
# 32. Phase 17 - Ablation & Generalization
# ===========================================================================
h1("32. Phase 17 - Ablation & Generalization")
h2("32.1 Motivation and Central Question")
body(
    "Phase 17 asks the question every earlier phase's own tuned numbers cannot answer by construction: does the "
    "governance defense stack detect the underlying MANIPULATION BEHAVIOR the seven attack families share, or "
    "merely the SURFACE characteristics of the specific artifacts it was built and tuned against? Signals were "
    "written FROM the seven known families' own real content (Section 26.2's admission-signal provenance); "
    "in-sample numbers on those same families cannot, by themselves, establish generalization. Phase 17 is "
    "organized around removing components one at a time (ablation) and testing the remaining stack against content, "
    "languages, memory foundations, and adversaries it was never tuned against (generalization)."
)
h2("32.2 Ablation")
body(
    "For every defense component (each admission signal group, each corroboration rule, the Sleeper signals, "
    "sibling propagation, and the B10 learned blend), Phase 17 removes it and re-measures detection/false-positive "
    "rate on the affected splits, with a Holm-corrected exact McNemar paired test against the full stack "
    "(`phase17/experiments.py`). Every rate throughout Phase 17 carries a Wilson 95% confidence interval "
    "(`phase17/stats.py`), and correlated samples (e.g. several LLM-paraphrased variants sharing one parent) use a "
    "cluster-robust bootstrap rather than a naive per-record interval -- closing a real, disclosed statistical-power "
    "gap Phase 6 first raised (a 15-record poison population is 6.7 percentage points per detection)."
)
h2("32.3 Generalization Hierarchy")
body(
    "Unseen attack family: `phase17/generalization.py::leave_one_family_out` removes exactly the admission signals "
    "written from one family's own content and re-measures that family's detection -- the classic leave-one-family-"
    "out shape, reusing Phase 11's own vocabulary. Unseen attack mechanism (a materially stronger test, since these "
    "mechanisms were never used to write ANY signal): 6 LLM-authored mechanisms x 10 scenarios "
    "(`phase17/novel_attacks.py`), later extended to a 37-group, dev-only mechanism pool "
    "(`phase17/dev_sets.py`/`dev_sets2.py`) used to tune a stacked embedding+judge detector under leave-mechanism-"
    "out cross-validation, so the detector never sees a demonstration from the mechanism it is scored on."
)
picture(f"{FIGDIR}/fig_novel_mechanism.png",
       "Figure 17 - Unseen-mechanism exclusion rose from 0/60 (the pre-Phase-17 live rule) to 19/60 (B11, a live "
       "judge plus a language-safe composition rule) to 35/60 (B12, a stacked embedding+judge detector), with 0 "
       "false positives on held-out benign populations at every step.")
body(
    "Automated leakage/contamination checks (`phase17/leakage_audit.py`) verify, for every real result reported in "
    "this section: zero conversation-id overlap between a detector's calibration data and its held-out "
    "false-positive-rate evaluation data; zero overlap between the poison-target conversations and the calibration "
    "negatives; and zero exact-text duplication between every dev/tuning set and every held-out evaluation split "
    "(455 dev texts vs. 351 eval texts checked, 0 overlap). These checks are wired into the automated test suite "
    "(Section 8's own testing discipline extended to Phase 17) so a future addition to either side cannot silently "
    "reintroduce a leak."
)
h2("32.4 Language Generalization")
body(
    "Chinese poison and benign populations (`phase17/perltqa.py`, `phase17/translation.py`) test the stack under a "
    "language it was never tuned on. The pre-Phase-17 live rule's retrieval-consensus signal produced a real, "
    "disclosed defect: 907 of 932 benign Chinese PerLTQA memories were falsely flagged, because a lexical/semantic "
    "divergence signal built for English is out-of-distribution for Chinese text. A language-safe composition rule "
    "(`GROUPED_GATED_ADMISSION_AND_RETRIEVAL_CORROBORATED`) that prevents retrieval-only evidence from excluding a "
    "memory on its own reduces this to 0/932 with no loss of English-language detection."
)
picture(f"{FIGDIR}/fig_chinese.png",
       "Figure 18 - Chinese poison exclusion across four Phase 17 rounds: a translate-then-score route and a "
       "zero-shot multilingual-embedding route catch different, only partially overlapping subsets (21 of 37 "
       "overlap); their union reaches 37/84 (44.0%), a real improvement over either individually, with 0/447 "
       "benign false positives maintained throughout.")
h2("32.5 Memory-Foundation Generalization")
body(
    "The defense stack was built and tuned entirely against a clean-agent candidate pool (Section 12); Phase 17 "
    "tests it against two real, independent, previously-unexercised memory foundations. A-mem-sys "
    "(`phase3/evaluation/foundations_real/amem_real_adapter.py`, run under an isolated environment, `C:\\h4venv`) "
    "was ingested and retrieved from live for 57 real stores: the defense excludes 9/9 real original poison cases "
    "on what A-mem-sys itself retrieves, though most evasion variants still evade, and A-mem-sys's own note-"
    "evolution mechanism was traced directly and confirmed to consistently return a genuine "
    "`should_evolve: false` decision for this content (a real model behavior, not a swallowed error). "
    "Mem0 (`phase3/evaluation/foundations_real/mem0_real_adapter.py`, LLM-free `infer=False` add path, real "
    "on-disk Qdrant plus real HuggingFace embeddings) was installed and exercised live for the first time in this "
    "project's history (a second isolated environment, `C:\\mem0venv`): the same 27 real Track B cases retrieve "
    "27/27 poison, and 18/27 (66.7%) are flagged, though 0/27 are excluded -- because Mem0's own real retrieval "
    "returns a smaller candidate pool (mean 3.56 items) than A-mem-sys's search did for identical inputs (4 items), "
    "which genuinely changes the pool-wide retrieval-consensus divergence score enough to stay below the "
    "exclusion band. This is reported as a real, disclosed memory-foundation-dependence finding, not a defect."
)
h2("32.6 Evaluator Independence, Nondeterminism, and the Security-Utility Frontier")
body(
    "The Track A answer-generating agent (`llama2`) and the Phase 17 judge/detector model (`qwen2.5:7b`) are "
    "different model families by default. A direct test of what happens if the SAME model self-judges its own "
    "answers found a real, measurable inflation: 100% self-judged correctness versus 93.3%-then-76.7% (as coverage "
    "was completed) independently-judged correctness on the identical 150 real answers -- a concrete argument "
    "against ever self-judging in a headline claim (`phase17/evaluator_independence.py`). Nondeterminism was turned "
    "from a disclosed caveat into a measured property: three repeated B0 runs on the same 150 real cases gave "
    "identical answer text in 139/150, with headline rates moving by roughly one case per run "
    "(`phase17/utility_repeats.py`). A security-utility frontier table (`phase17/security_utility_frontier.py`) "
    "reports detection, false-positive rate, utility, and a per-memory latency note for every live config side by "
    "side, deliberately never naming one configuration as universally best."
)
h2("32.7 Adaptive Attackers and Adversarial Provenance Integrity")
body(
    "47 LLM-rewritten, defense-aware paraphrase variants of the 24 signal-source/regenerated poison records test "
    "whether the stack detects manipulation behavior or surface artifacts. A direct entailment check "
    "(`phase17/adaptive_attacker.py`) confirms all 47/47 variants still semantically assert their parent's forged "
    "claim, so the measured drop in detection on them is a genuine evasion of the defense, not a broken attack. A "
    "genuine provenance-based fix was found for a subset of these: the 13 poison parents built from a real LoCoMo "
    "question-answer pair each have a real, empirically-located home conversation "
    "(`phase17/evasion_real_context.py`); using that conversation's own 369-680 real turns as the earlier evidence "
    "a conflict-detection check compares against (rather than three unrelated distractors) raises exclusion on "
    "those 26 variants from 3/26 to 6/26, driven entirely by the one family (FARMA) that explicitly appeals to "
    "forged prior authority."
)
body(
    "Adversarial provenance/metadata integrity was stress-tested directly (`phase17/provenance_integrity.py`): "
    "every attempt to smuggle an evaluator-only field (including a simulated `attacker_originated=False` claim) "
    "into a real risk-scoring call is confirmed rejected by frozen, pre-existing code "
    "(`EvaluatorOnlyLeakageError`/`FORBIDDEN_SIGNAL_KEYS`, Section 25.1) -- this round PROVES the existing guard "
    "fires, it adds no new one. At the content level, five deliberately constructed forged-metadata sentences (a "
    "fake memory-id citation, a fake timestamp, a fake authorization code, a stale-replay claim, and a fake "
    "parent-lineage claim) were tested against the live defenses: the pre-Phase-17 rule is fooled by 4 of 5; a new "
    "judge tier added specifically for lineage-citation claims closes the remaining gap, reaching 5/5, with 0 false "
    "positives on a matched benign negative control (genuine dates, confirmations, and codes)."
)
h2("32.8 The AgentPoison Query-Side Trigger: A Deep Dive That Changed the Conclusion")
body(
    "AgentPoison's real mechanism is a gradient-optimized, deliberately nonsensical trigger phrase ('regulates ned "
    "kane seized buffalo 1916...') intended to make its embedding a broadly-retrievable 'universal magnet' across "
    "many unrelated queries -- a query-side attack surface no defense component in this stack was ever built to "
    "examine. Three content/embedding-space heuristics were tried and failed for identifiable reasons: a "
    "diverse-query similarity mean under this project's own default judge embedding model; the same test under the "
    "REAL model the trigger was gradient-optimized against (`all-MiniLM-L6-v2`, confirmed by inspection of "
    "`phase4/attacks/agentpoison/trigger_run.py`), which proved undiscriminating under that model's own baseline "
    "similarity distribution; and the attacker's own real optimization objective inverted (distance from real "
    "benign-content cluster centroids), which does flag AgentPoison but non-specifically -- it also flags all six "
    "other families and 8% of real benign text."
)
body(
    "The fourth attempt found the missing piece: this project's OWN live retrieval-consensus signal "
    "(Section 21.1) already uses `all-MiniLM-L6-v2` -- the same model the trigger targets -- and the correct test "
    "of a 'universal magnet' is retrieval FREQUENCY across diverse unrelated queries, not raw similarity magnitude. "
    "A direct behavioral test (one shared candidate pool containing the real AgentPoison memory, one real memory "
    "from each other family, and 50 real benign memories, ranked against 300 diverse real LoCoMo questions from "
    "unrelated conversations) found that AgentPoison's reconstructed trigger has the LOWEST top-3 retrieval rate of "
    "all seven families."
)
picture(f"{FIGDIR}/fig_agentpoison.png",
       "Figure 19 - AgentPoison's reconstructed trigger is retrieved into the top 3 for only 9.7% of 300 diverse, "
       "unrelated real queries, the lowest of all seven families (25.3%-37.3%) and only slightly above real benign "
       "memories (2.0%). This project's reconstruction does not exhibit the broad-retrievability property the real "
       "attack's gradient optimization is designed to produce.")
body(
    "This changes the conclusion materially: rather than \"no defense exists for this attack surface\" (three "
    "failed detectors), the honest, measured conclusion is that this benchmark's reconstruction of AgentPoison -- "
    "built with a disclosed, limited number of optimization iterations rather than the real paper's full white-box "
    "gradient search -- does not empirically manifest the specific behavior a dedicated defense would need to "
    "catch, and its content-level template is already caught by an existing admission signal "
    "(`forged_provenance_confirmation_score`, confirmed firing at 1.0). A future, more faithfully-optimized "
    "AgentPoison artifact would need to be re-tested with this SAME retrieval-frequency method, not the earlier "
    "similarity-magnitude heuristics, which this phase's own record now shows do not work for this mechanism."
)
h2("32.9 Sanity Baselines, the Canonical Matrix, and Benchmark Packaging")
body(
    "Explicit reference bounds (`phase17/sanity_baselines.py`) -- ALWAYS_ALLOW (identical to B0 by definition), "
    "ALWAYS_QUARANTINE, and a RANDOM_BUDGET_MATCHED baseline that flags memories at the same rate a real detector "
    "does, uniformly at random -- are reported alongside every real number, never ranked as competitors. At B12's "
    "own real alert rate on held-out novel mechanisms (11.4%), a random detector at that same budget catches a mean "
    "of 11.1% of the poison; B12's real detection is 58.3%, clearly outside the random 95% range, confirming its "
    "detection is not attributable merely to a high alert rate. A scoped canonical result matrix "
    "(`phase17/canonical_matrix.py`, 36 rows) and a minimal, tested benchmark runner "
    "(`phase17/bench_runner.py`, `python -m phase17.bench_runner --defense B12 --split held_out_novel`) give this "
    "project a forward-facing, reproducible entry point; `docs/phase17/BENCHMARK_SPECIFICATION.md` and "
    "`docs/BENCHMARK_CARD.md` document the schema, threat model, and known limitations for a future user of this "
    "benchmark who is not the original author."
)
h2("32.10 Five Rounds of Fixes: What Was Genuinely Resolved and What Remains Open")

table(
    ["Round", "Trigger", "Key real result"],
    [
        ["1", "Implement ablation + generalization", "Unseen-mechanism exclusion 0/60; Chinese benign FPR 907/932 (defect found)"],
        ["2", "\"Fix the negative results\"", "Language-safe rule -> Chinese benign FPR 0/932; stacked detector (B12) -> unseen-mechanism exclusion 35/60"],
        ["3", "\"Fix everything left, incl. Mem0/3rd model/Gemini\"", "Mem0 installed and run live for the first time; phi3:mini + Gemini added; random-budget-matched baseline run"],
        ["4", "Deep dive on 3 unresolved items", "Root-caused (not just re-tried) preference-hijack confound, evasion's real-conversation fix, AgentPoison's wrong-embedding-model mistake"],
        ["5", "Fix the 2 items still flagged", "AgentPoison: correct retrieval-frequency test changes the conclusion (Section 32.8); human eval: 60/60 proxy coverage + a second independent proxy"],
    ],
    caption="Table 1 - Phase 17's five rounds of fixes (full detail: docs/phase17/PHASE17_*.md).",
)

body(
    "What remains genuinely open, disclosed rather than hidden: defense-aware paraphrase of non-contradictory "
    "claims and additive fabrications (a memory that adds a plausible-sounding but unverifiable detail) cannot be "
    "resolved by content analysis alone -- they need real provenance/timestamp evidence this benchmark's arenas do "
    "not uniformly carry; a fabricated long-standing preference is close to indistinguishable from a genuine one "
    "from text alone (a real, deconfounded test using 100% human-written LoCoMo text found a clean corroboration "
    "signal in principle -- real poison is 9/9 zero-corroborated versus 11/151 for genuine preferences -- but it "
    "cannot be applied to the standalone, LLM-authored preference-hijack evaluation instances, which have no real "
    "conversational history to check against by the harness's own design); and a real, blinded human evaluation of "
    "this project's own answer-correctness judgments remains open (a genuine 60-item blinded packet exists and is "
    "ready for a human rater; two independent LLM proxies -- Gemini and phi3:mini, agreeing with each other 93.3% "
    "of the time -- provide an interim reference point but are explicitly not a substitute)."
)

# ===========================================================================
# 33. Overall Conclusion Across Phases 1-17
# ===========================================================================
h1("33. Overall Conclusion Across Phases 1-17")
body(
    "MAMBench, as of Phase 17, is a benchmark that reports where its own defenses generalize and where they do not, "
    "rather than one that reports only favorable numbers. The clean-agent foundation (Phases 1-3) and seven "
    "attack reconstructions (Phase 4) established a comparable, reproducible footing; the governance defense stack "
    "(Phases 5-13) closed the original threat model with admission, retrieval, propagation, sleeper, attribution, "
    "and adaptive-risk components; Phases 14-16 measured real, live cost and utility; and Phase 17's ablation and "
    "generalization work is this project's most direct answer to whether any of it actually generalizes. The "
    "answer is disclosed as genuinely mixed: mechanism-level, judge-plus-embedding detection generalizes far "
    "better than the original family-tuned signal set, several real defects (a 907/932 benign false-positive rate "
    "under language shift; several forged-metadata gaps) were found and fixed with measured, honest evidence, and "
    "a small number of problems -- defense-aware paraphrase of non-contradictory claims, additive fabrication, and "
    "AgentPoison's specific reconstruction fidelity -- remain open with a precise, substantiated reason rather than "
    "a vague caveat. Every number in Sections 29-33 traces to a persisted artifact under `phase17/data/`, `phase14/"
    "data/`, or `phase15/data/`, and the full cross-phase regression suite (2,722 tests as of the last Phase 17 "
    "change) passed with zero failures after every shared-code edit reported here."
)

doc.save(PATH)
print("Stage 2 done.")
