"""Build MAMBench_Comprehensive_Project_Documentation.docx -- the one comprehensive project document.

    python scripts/build_comprehensive_documentation.py

The Methodology Draft and the Results Analysis stay separate and authoritative; this document
summarises them and everything else a new researcher or engineer needs. Narrative text is written
here; every table that can drift is generated at build time from the repository itself:
phases from the Methodology's headings, references from its reference list and
RELATED_WORK_AND_NOVELTY.md, hold-outs from the freeze records, the benchmark from
mambench/registry.json, formulas from phase17/formulas.py, defence configurations from
phase14/defended_retrieval.py, CI from .github/workflows/tests.yml, licences from
DATA_LICENSING_AND_ANNOTATION_AUDIT.md, and the source mapping from docs/cleanup/CLEANUP_INVENTORY.md.
"""
from __future__ import annotations

import importlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import docx
from docx.enum.section import WD_ORIENT  # noqa: F401  (kept for readers extending the layout)
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "MAMBench_Comprehensive_Project_Documentation.docx"
METHODOLOGY = ROOT / "Methodology Draft.docx"
RESULTS = ROOT / "MAMBench Results Analysis.docx"
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)


# --- document helpers -----------------------------------------------------------------

def _styles(d):
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    st.paragraph_format.space_after = Pt(5)
    st.paragraph_format.line_spacing = 1.12
    for lvl, size in ((1, 16), (2, 13), (3, 11)):
        h = d.styles[f"Heading {lvl}"]
        h.font.name, h.font.size, h.font.color.rgb = "Calibri", Pt(size), ACCENT
        h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
        h.paragraph_format.space_before = Pt(14 if lvl == 1 else 10)
        h.paragraph_format.space_after = Pt(4)
    for sec in d.sections:
        sec.left_margin = sec.right_margin = Cm(2.2)
        sec.top_margin = sec.bottom_margin = Cm(2.0)


def _field(run, code):
    for kind, text in (("begin", None), (None, code), ("separate", None), (None, "1"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        elif text == code:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = f" {code} "
        else:
            el = OxmlElement("w:t")
            el.text = text
        run._r.append(el)


def _footer(d):
    p = d.sections[0].footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("MAMBench — Comprehensive Project Documentation · page ")
    r.font.size = Pt(8)
    r2 = p.add_run()
    r2.font.size = Pt(8)
    _field(r2, "PAGE")


class Doc:
    def __init__(self):
        self.d = docx.Document()
        _styles(self.d)
        _footer(self.d)

    def h(self, text, level=1):
        self.d.add_heading(text, level=level)

    def p(self, text, bold_lead=None, italic=False):
        para = self.d.add_paragraph()
        if bold_lead:
            para.add_run(bold_lead).bold = True
        r = para.add_run(text)
        r.italic = italic
        return para

    def bullets(self, items):
        for it in items:
            if isinstance(it, tuple):
                para = self.d.add_paragraph(style="List Bullet")
                para.add_run(it[0]).bold = True
                para.add_run(it[1])
            else:
                self.d.add_paragraph(it, style="List Bullet")

    def numbered(self, items):
        for it in items:
            self.d.add_paragraph(it, style="List Number")

    def code(self, text):
        para = self.d.add_paragraph()
        r = para.add_run(text)
        r.font.name, r.font.size = "Consolas", Pt(9)
        para.paragraph_format.left_indent = Cm(0.6)
        return para

    def table(self, rows, widths=None, header=True, size=8.5):
        t = self.d.add_table(rows=len(rows), cols=len(rows[0]))
        t.style = "Light Grid Accent 1"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                cell = t.cell(i, j)
                cell.text = ""
                run = cell.paragraphs[0].add_run(str(val))
                run.font.size = Pt(size)
                run.bold = header and i == 0
                if widths:
                    cell.width = Cm(widths[j])
        self.d.add_paragraph()
        return t

    def figure(self, path, caption, width_cm=15.5):
        if not path.is_file():
            self.p(f"[Figure not found: {path.relative_to(ROOT)}]", italic=True)
            return
        self.d.add_picture(str(path), width=Cm(width_cm))
        self.d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = self.p(caption, italic=True)
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def page_break(self):
        self.d.add_page_break()

    def save(self, path):
        self.d.core_properties.title = "MAMBench — Comprehensive Project Documentation"
        self.d.core_properties.subject = "Memory and Agent Manipulation Benchmark"
        self.d.save(str(path))


# --- data drawn from the repository -----------------------------------------------------

def _docx_section(path, heading_prefix):
    d = docx.Document(str(path))
    out, inside = [], False
    for p in d.paragraphs:
        style = p.style.name if p.style is not None else ""
        if style == "Heading 1":
            inside = p.text.startswith(heading_prefix)
            continue
        if inside and p.text.strip():
            out.append(p.text.strip())
    return out


def phase_rows():
    d = docx.Document(str(METHODOLOGY))
    rows = [["Section", "Phase / layer", "Methodology heading"]]
    for p in d.paragraphs:
        if p.style is not None and p.style.name == "Heading 1":
            m = re.match(r"(\d+)\. (Phase \d+|Attribution)\s*[—–-]+\s*(.+)", p.text)
            if m:
                rows.append([m.group(1), m.group(2), m.group(3)])
    return rows


def references():
    meth = _docx_section(METHODOLOGY, "16. References")[1:]  # first paragraph is the verification note
    seen = set(re.findall(r"arXiv:(\d{4}\.\d{4,5})", " ".join(meth)))
    rel = []
    txt = (ROOT / "RELATED_WORK_AND_NOVELTY.md").read_text(encoding="utf-8")
    block = txt.split("## 1. The papers", 1)[1].split("## 2.", 1)[0]
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in ("Key", "---") or set(cells[0]) <= {"-"}:
            continue
        arx = re.findall(r"arXiv:(\d{4}\.\d{4,5})", cells[1])
        if arx and arx[0] in seen:
            continue
        rel.append(f"{re.sub(r'[*]', '', cells[1])} ({cells[2]}).")
    return meth, rel


def holdout_rows():
    reg = json.loads((ROOT / "mambench" / "registry.json").read_text(encoding="utf-8"))
    mods = next(t for t in reg["tasks"] if t["id"] == "integrity.holdout_freeze_digests")["params"]["modules"]
    rows = [["Frozen corpus (module)", "Items", "Frozen (UTC)", "sha256 (first 16)"]]
    for m in mods:
        fz = json.loads(importlib.import_module(m).FREEZE.read_text(encoding="utf-8"))
        n = fz.get("n") or fz.get("n_attacks") or fz.get("n_items") or ""
        if "n_attacks" in fz and "n_benign" in fz:
            n = f"{fz['n_attacks']} attacks + {fz['n_benign']} benign"
        rows.append([m.replace("phase17.", ""), n, fz.get("frozen_utc", ""), fz["sha256"][:16]])
    return rows


def benchmark_rows():
    reg = json.loads((ROOT / "mambench" / "registry.json").read_text(encoding="utf-8"))
    tasks = [["Task", "Track", "Split role", "Requires", "Metrics"]]
    for t in reg["tasks"]:
        tasks.append([t["id"] + (" (UNSUPPORTED)" if t.get("supported", True) is False else ""), t["track"],
                      t["split_role"], ", ".join(t["requires"]) or "—", ", ".join(t["metrics"]) or "—"])
    metrics = [["Metric", "Kind", "Definition (numerator / denominator for proportions)"]]
    for name, m in reg["metrics"].items():
        dfn = f"{m['numerator']} ÷ {m['denominator']}" if m["kind"] == "proportion" else m["definition"]
        metrics.append([name, m["kind"], dfn])
    return reg, tasks, metrics


def formula_rows():
    from phase17.formulas import rows
    return rows()


DEFENCE_SUMMARY = {
    "B0": "no defence", "B1": "admission guard only", "B2": "retrieval-consensus guard only",
    "B3": "propagation-containment guard only", "B4": "admission + retrieval", "B5": "retrieval + propagation",
    "B6": "admission + propagation", "B7": "admission + retrieval + propagation",
    "B8": "B7 + sleeper guard (all four Phase 6 guards)", "B9": "cross-guard risk composition (Phase 10)",
    "B10": "learned GNN/GLN blend with an untrained z-score corroboration gate (Phase 11)",
    "B11": "Phase 17 generalisation fix (judge tiers)", "B12": "stacked detector (Phase 17 round 4)",
    "B13": "provenance-aware admission: channel trust + owner-conversation corroboration",
    "B14": "calibrated fusion of eleven intent/effect signals incl. three published detectors",
    "B15": "lean refit: deberta backbone + this project's own signals, no LLM prompts",
    "B16": "B15 + rejection ledger (stateful; refuses semantic neighbours of rejected content)",
    "B17": "union of B13 and B14", "B18": "B17 + ProtectAI deberta at a frozen threshold (not recommended)",
    "B19": "memory-shape gate in front of B13 (non-memories refused as MALFORMED)",
}


def defence_rows():
    from phase14.defended_retrieval import REAL_CONFIGS
    rows = [["Configuration", "What it is"]]
    rows += [[c, DEFENCE_SUMMARY.get(c, "see phase14/defended_retrieval.py")] for c in REAL_CONFIGS]
    return rows


def ci_rows():
    wf = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    jobs = re.findall(r"^  ([a-z0-9-]+):\n    name: (.+)$", wf, flags=re.M)
    return [["CI job", "What it checks"]] + [[j, n] for j, n in jobs]


def licence_rows():
    txt = (ROOT / "DATA_LICENSING_AND_ANNOTATION_AUDIT.md").read_text(encoding="utf-8")
    block = txt.split("### 1.2", 1)[1].split("### 1.3", 1)[0]
    rows = [["Dataset", "Owner", "Licence / terms", "Redistribute?"]]
    for line in block.splitlines():
        cells = [c.strip().replace("**", "") for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] not in ("Component",) and not set(cells[0]) <= {"-"}:
            rows.append(cells[:4])
    return rows


def inventory_counts():
    txt = (ROOT / "docs" / "cleanup" / "CLEANUP_INVENTORY.md").read_text(encoding="utf-8")
    rows = [["Classification", "Files"]]
    for line in txt.split("## Summary", 1)[1].split("## Every file", 1)[0].splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[1].isdigit():
            rows.append(cells)
    return rows


# --- content ----------------------------------------------------------------------------

def build() -> Path:
    D = Doc()
    d = D.d
    t = d.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("MAMBench — Memory and Agent Manipulation Benchmark")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(22), ACCENT
    s = d.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s.add_run("Comprehensive Project Documentation").font.size = Pt(14)
    m = d.add_paragraph()
    m.alignment = WD_ALIGN_PARAGRAPH.CENTER
    m.add_run(f"Generated {date.today().isoformat()} by scripts/build_comprehensive_documentation.py").italic = True
    D.p("This document is the single entry point to the project. Two documents remain separate and "
        "authoritative: the Methodology Draft (Methodology Draft.docx) for research methods and "
        "procedures, and the Results Analysis (MAMBench Results Analysis.docx) for every result with "
        "its denominators, intervals and qualifications. Where this document summarises a number, "
        "those documents hold its full context. Tables marked as generated are built from the "
        "repository at build time.", italic=True)
    D.h("Contents", 1)
    for part in ("Part I — Project Overview", "Part II — Background and Security Context",
                 "Part III — Research Evolution and Methodology", "Part IV — Unified Benchmark",
                 "Part V — Implementation and Architecture", "Part VI — Results and Evidence",
                 "Part VII — Reproducibility and Operations", "Part VIII — Research Governance and Release Readiness",
                 "Part IX — Limitations and Future Work", "Part X — References and Appendices"):
        D.bullets([part])
    D.page_break()

    # PART I -----------------------------------------------------------------------------
    D.h("Part I — Project Overview", 1)
    D.h("1. Project identity", 2)
    D.p("MAMBench (Memory and Agent Manipulation Benchmark) is a research benchmark for memory poisoning "
        "and manipulation attacks against large-language-model agents that keep a persistent, external "
        "memory. The repository contains the frozen victim agent, seven reconstructed attacks, a layered "
        "defence stack, instrumentation and attribution layers, frozen hold-out corpora, and the unified "
        "benchmark runner (python -m mambench).")
    D.h("2. Executive summary", 2)
    D.bullets([
        ("Scope. ", "Seventeen phases: data foundations (1–2), a clean memory-augmented agent (3), seven attacks (4), "
                    "instrumentation and attribution (5), defences, monitoring and forensics (6–13), utility, integrated "
                    "and final evaluation (14–16), and ablation and generalisation with seven external review rounds (17), "
                    "followed by six pre-registered defence programmes (v2–v7) targeting three research gaps."),
        ("Measurement first. ", "A causal, pre-committed audit found that only 42.5% of 2,628 attack instances both subvert an "
                               "undefended agent and implement their labelled mechanism (435–944 depending on how disputed "
                               "labels resolve), so detection rates are reported on both the full and the working-attack denominator."),
        ("Defences. ", "Provenance-aware admission (B13) reaches attack classes that content-only detection cannot; a rejection "
                       "ledger reduces adaptive evasion from 24.6% to 0.8% at an explicit denial-of-service cost; the best "
                       "configurations for memory poisoning and for injection-shaped text are complementary, not ranked."),
        ("Research gaps. ", "Under a rubric fixed before the final programmes, operational closure is 75.0% for provenance and "
                            "governance, 71.2% for self-propagation and containment, and 33.8% for dormant and implicit "
                            "sleepers (Defence v7, 2026-10-17). The sleeper gap is not closed."),
        ("Benchmark. ", "mambench/ registers 7 tracks and 19 tasks with explicit statuses and denominators; CI runs every test "
                        "suite, a strict smoke run, and the held-out split evaluations against digest-verified LoCoMo."),
    ])
    D.h("3. Problem statement and motivation", 2)
    D.p("Agents that write conversation history, task outcomes or retrieved documents into memory inherit an attack "
        "surface stateless systems do not have: content an adversary places in memory can redirect the agent long "
        "after the interaction that planted it, and can spread into derived memories. Published attacks (AgentPoison, "
        "MINJA, DSRM, MemoryGraft, FARMA, MPBench, Sleeper Memory Poisoning) target different points of this pipeline "
        "and were evaluated against different agents and memory systems, so their severity, and any defence against "
        "more than one of them, could not be compared. MAMBench provides one frozen agent, one memory representation, "
        "one evaluation protocol and one result schema for all of them.")
    D.h("4. Research objectives and scope", 2)
    D.p("The research questions of the Results Analysis are the working objectives:")
    D.numbered(["RQ1 — How many of the benchmark's attacks function, and what does that do to published detection rates?",
                "RQ2 — Does provenance-aware admission reach attack classes content-only detection cannot, at acceptable cost?",
                "RQ3 — Do the defences generalise across independently authored attack corpora, and if not, why?",
                "RQ4 — Do bespoke defences beat published off-the-shelf detectors on this threat model?",
                "RQ5 — Can a stateful defence blunt a query-based adaptive attacker?",
                "RQ6 — Do pre-registered defence programmes, each scored once on fresh held-out data under a frozen rubric, "
                "close the three research gaps?"])
    D.p("Out of scope: production systems (all attacks ran only against local, offline infrastructure), tool-executed "
        "memory writes, session compaction and skill synthesis (the four inapplicable MPBench classes), and frontier "
        "agents (every agent-side number is for a 7–8B local model).")
    D.h("5. Threat model and assumptions", 2)
    D.p("An adversary controls content on an untrusted channel — a shared document, a tool output, a retrieved web "
        "page, or a query to the agent — but not the memory store, the agent's weights or the defence. Channel labels "
        "recorded by the memory system are assumed correct; attacks relayed through the user's own channel are a "
        "documented boundary (0/24 caught by every provenance defence). Ground truth (whether a memory is poison, and "
        "from which family) is evaluator-only: it is never passed to a decision function, which is enforced in code "
        "(FORBIDDEN_SIGNAL_KEYS / EvaluatorOnlyLeakageError) and checked by the benchmark task "
        "provenance.evaluator_field_rejection.")
    D.p("The memory lifecycle every attack and defence is placed on:")
    D.code("injection → admission → storage → retrieval → selection → exposure/use → propagation → influence → detection → attribution")
    D.h("6. Intended users and applications", 2)
    D.bullets(["Researchers comparing memory-poisoning attacks or defences on a common agent and protocol.",
               "Defence developers who need false-positive costs, working-attack denominators and held-out discipline.",
               "Engineers auditing a memory-augmented agent's admission, retrieval and consolidation paths.",
               "Reviewers reproducing a reported number from its counts (every formula names the code that computes it)."])
    D.h("7. Contributions, with qualifications", 2)
    D.p("Classifications follow the primary-source comparison in RELATED_WORK_AND_NOVELTY.md; several elements are "
        "adaptations or replications of prior work and are labelled as such.")
    D.table([["Contribution", "Classification", "Qualification"],
             ["Re-scoring defences on a causal working-attack subset", "New method / finding", "Working set depends on probe and judge (435–944 of 2,628)"],
             ["Separating channel trust from owner-conversation corroboration on single-use hold-outs", "New empirical finding", "Channel trust alone adds no recall"],
             ["Owner-conversation NLI corroboration at admission", "Adaptation / engineering", "Close to fact-verification use of NLI"],
             ["Laundering through consolidation; taint decay across generations", "Replication + new measurement", "Named and defended by MemLineage, TMA-NM, PPMF"],
             ["Benign conditional look-alikes and implicit-intent sleepers", "New evaluation design", "Sleeper dormancy itself is a replication"],
             ["Rejection ledger", "Application of prior work", "Stateful detection precedents exist"],
             ["Neutralisation frame", "Application", "Spotlighting precedent"],
             ["Unified benchmark with explicit statuses and denominators", "Engineering contribution", "Registry counts what runs; no single score"]],
            widths=[6.5, 4, 6.5])

    # PART II ----------------------------------------------------------------------------
    D.h("Part II — Background and Security Context", 1)
    D.h("8. AI-agent security concepts used here", 2)
    D.bullets([("Admission: ", "the decision to store a candidate memory."),
               ("Retrieval and selection: ", "ranking candidate memories for a query, then choosing the top-k shown to the agent."),
               ("Exposure versus influence: ", "a memory shown to the agent is exposed; influence requires a counterfactual change in the answer."),
               ("Provenance: ", "the recorded channel and principal a memory came from; corroboration asks whether the owner's own conversation supports it."),
               ("Propagation: ", "derived memories (summaries, consolidations) carrying a poisoned payload forward through generations."),
               ("Sleeper: ", "a harmless-looking memory that activates on a later, semantically related query.")])
    D.h("9. Memory poisoning and manipulation: the seven attacks", 2)
    D.table([["Attack", "Capability", "Mechanism", "Status in MAMBench"],
             ["AgentPoison", "white-box", "gradient-optimised retrieval trigger", "Reconstruction with limited optimisation; does not show the 'universal magnet' property"],
             ["MINJA", "query-only", "agent-mediated insertion through ordinary queries", "Reconstructed"],
             ["FARMA", "black-box", "forged reasoning traces with self-referential amplification", "Reconstructed"],
             ["MemoryGraft", "gated", "LLM-judged forged 'successful experience' records", "Reconstructed"],
             ["DSRM", "black/white-box", "adversarial decision construction", "Reconstructed"],
             ["MPBench-PCFI", "black-box", "unmarked fabricated facts", "2 of 6 classes apply; 4 need write channels this agent lacks (UNSUPPORTED)"],
             ["Sleeper Memory Poisoning", "external manager", "dormant, trigger-activated write instructions in documents", "Reconstructed"]],
            widths=[3.2, 2.4, 5.2, 6.2])
    D.p("Phase 17 added novel-mechanism populations (authority impersonation, conditional backdoor, exfiltration "
        "instruction, memory worm, policy revocation, preference hijack), externally authored corpora, Chinese-language "
        "poison and human-written jailbreak hold-outs; phase17/data/attack_register.json lists every population, its "
        "author, and whether it was validated and run against an undefended agent.")
    D.h("10. Retrieval, attribution and provenance", 2)
    D.p("The attribution layer answers six questions separately and never merges them into one verdict: origin, "
        "lineage, propagation, exposure, influence and references. Phase 9 composes them into a backward walk from a "
        "flagged incident whose confidence follows a worst-hop-wins rule. Provenance is recorded at write time in a "
        "ledger; since Defence v7 the ledger is hash-chained so edits, deletions, reordering and truncation are detected.")
    D.h("11. Tool-use and action-selection risks", 2)
    D.p("Exfiltration and standing-instruction attacks aim at actions rather than answers. On gate-valid exfiltration "
        "instances, three 7–8B agent families restated the attacker's directive but did not execute the redirect "
        "(zero harm). A high-impact action gate was built for sleeper activation but its test was under-powered "
        "(one harmful action undefended). Tool-executed memory writes are outside the victim architecture.")
    D.h("12. Agentic-AI security taxonomies", 2)
    D.p("The project's own taxonomy is the memory lifecycle above, with attacks classified by attacker capability "
        "(white-box, black-box, query-only, gated, external manager) and by the stage they target. The six-class "
        "MPBench taxonomy is used for fabricated-fact attacks; Phase 1 registered MemSecBench, MEMSAD, MemAudit, "
        "A-MemGuard, ASB, AgentDojo and InjecAgent as evaluation and comparison resources.")
    D.h("13. Relationship to existing benchmarks and detectors", 2)
    D.p("RELATED_WORK_AND_NOVELTY.md compares MAMBench with sixteen recent works from their primary sources "
        "(demonstrated / partial / not demonstrated / unclear for each capability). Published prompt-injection "
        "detectors were run as baselines (ProtectAI deberta-v3, Llama Guard 3, a plain 'is this malicious?' prompt): "
        "disaggregated, the project's configurations lead the strongest published baseline by 32.1 (B13) to 37.2 (B17) "
        "points on memory poisoning, and trail an off-the-shelf classifier on one injection corpus that is plausibly in "
        "its training data. The pooled comparison should not be cited in either direction.")
    D.h("14. Literature", 2)
    D.p("All cited works are listed in Part X (section 90), drawn from the Methodology's verified reference list and the "
        "related-work comparison.")

    # PART III ---------------------------------------------------------------------------
    D.h("Part III — Research Evolution and Methodology", 1)
    D.h("15. Research roadmap and phase history (generated)", 2)
    D.table(phase_rows(), widths=[1.6, 2.8, 12.6])
    D.p("After Phase 17, an independent review (2026-10-12) led to a remediation, a gap-closure round, a targeted phase "
        "and six pre-registered defence programmes (v2–v7, 2026-10-13 to 2026-10-17), recorded in "
        "REMEDIATION_MASTER_REGISTER.md and in Results Analysis Sections 15–24.")
    D.figure(ROOT / "docs" / "figures" / "figure1_pipeline_phases_1_13.png", "Figure 1. Pipeline, Phases 1–13 (from the Methodology).")
    D.h("16. Original prototypes and initial hypotheses", 2)
    D.p("Phase 3 reached its final victim architecture, V3-Hybrid, through five validated iterations (hybrid retrieval "
        "reranking, deterministic temporal resolution, a bounded evidence-scoped verification step). The initial "
        "hypotheses were the Methodology's RQ1–RQ4 (retrieval versus reasoning bounds, verification benefit, "
        "string versus semantic correctness metrics, Mem0 versus A-MEM); Phase 17 added RQ5 (does the defence detect "
        "shared manipulation behaviour or only tuned surface features).")
    D.h("17. Architecture evolution", 2)
    D.bullets(["Phases 6–10: four rule-based guards (admission, retrieval consensus, propagation containment, sleeper), then a cross-guard risk composition (B9).",
               "Phase 11: learned GNN/GLN components; six negative or mixed results preceded a score-composition fix; the learned models stay at parity.",
               "Phase 12: a fifth component, the Consolidation Guard, re-checks a derivation's sources before persistence.",
               "Phase 17: judge tiers (B11/B12), provenance-aware admission (B13), fusion and union configurations (B14–B19), the rejection ledger.",
               "Defence v2–v7: lineage verification, multi-generation containment, graded provenance, no-decay containment, two-stage sleeper frame, tamper-evident ledger."])
    D.figure(ROOT / "docs" / "figures" / "v7" / "W5_architecture_v7.png", "Figure 2. Defence architecture after Defence v7.")
    D.h("18. Major design decisions", 2)
    D.table([["Decision", "Justification"],
             ["Freeze each phase and add, never rewrite", "Later findings are dated notes, so the historical record stays checkable"],
             ["Evaluator-only ground truth", "Prevents a defence from seeing labels; enforced in code and by a benchmark task"],
             ["Report both denominators", "Detection over non-functional attacks measures response to inert text"],
             ["Freeze hold-outs by sha256 before scoring; pre-register predictions", "Prevents tuning on evaluation data; a reused hold-out (3) was retired"],
             ["Frozen evidence rubric for gap closure", "Scores measure evidence strength, decided before outcomes; critical capabilities cap the score"],
             ["Different model families for agent, judge and author", "A model never judges text it wrote"],
             ["Unified benchmark wraps frozen components", "No second implementation of attacks or defences to drift from the first"]],
            widths=[6.5, 10.5])
    D.h("19. Experimental design", 2)
    D.p("Paired designs on fixed populations (each item scored under both arms) with exact McNemar tests; Holm correction "
        "across each pre-registered family; power checks before paired designs; a measured noise floor for LLM-generated "
        "quantities; and held-out corpora scored once under committed predictions. Agent-side measurement uses "
        "qwen2.5:7b; judging uses a different family; generation for hold-outs uses families that never judge their "
        "own text.")
    D.h("20. Datasets and corpus construction", 2)
    D.p("Phases 1–2 built a provenance-preserving, schema-unified corpus of 1,266,194 conversational memory records from "
        "LoCoMo, LongMemEval, MSC and Conversation Chronicles (Methodology Sections 5–11). Attack populations were "
        "generated by the attacks' own injectors and, in Phase 17, by several model families and external sources; "
        "benign false-positive populations include ordinary memories, legitimate standing instructions and matched "
        "benign halves of hold-outs.")
    D.h("21. Attack families and threat scenarios", 2)
    D.p("See section 9 for the seven founding families and Phase 17's additions. Each population is audited for "
        "mechanism validity and for whether it changes an undefended agent's answer; non-working attacks are reported, "
        "not dropped.")
    D.h("22. Defences and mitigation strategies (generated)", 2)
    D.table(defence_rows(), widths=[3, 14])
    D.p("Defence programmes v2–v7 add mechanisms that are evaluated as conditions rather than numbered configurations: "
        "graded provenance (exclude / frame / keep), no-decay containment with a sentence-level fingerprint (ND|RAR-S), "
        "lineage recovery after deletion (DCR-2), the two-stage sleeper frame, the high-impact gate and the "
        "hash-chained provenance ledger.")
    D.h("23. Evaluation protocols", 2)
    D.bullets(["Detection: a defence's action on each poison and benign item; 'flagged' means any action other than ALLOW, 'excluded' means QUARANTINE or BLOCK.",
               "Attack validity: a two-arm causal audit (memory present versus absent) plus a mechanism check by a third model family.",
               "Harm: an agent task answered with and without the poison, judged by an LLM judge validated against human labels.",
               "Containment: payload-carrying descendants withheld at each generation of consolidation.",
               "Attribution: origin, lineage and propagation recovered from persisted ledgers and checked against injection-time ground truth."])
    D.h("24. Metrics and statistical methods (generated)", 2)
    D.table(formula_rows(), widths=[4.2, 8.3, 4.5], size=7.5)
    D.p("Gap closure: Gap score = Σ weightᵢ × scoreᵢ with scoreᵢ ∈ {0, 0.25, 0.5, 0.75, 1}; capped at 0.50 if any "
        "critical capability scores 0 and at 0.60 if any scores ≤ 0.25 (FINAL_DEFENCE_BASELINE_AUDIT.md §3). Scores "
        "measure evidence strength, not accuracy.")
    D.h("25. Baselines and comparison methodology", 2)
    D.p("B0 (no defence) is the baseline for every defence comparison; published detectors are run unchanged as external "
        "baselines; reference bounds ALWAYS_ALLOW, ALWAYS_QUARANTINE and a random detector matched to the alert rate are "
        "reported beside detection numbers (phase17/sanity_baselines.py). Configurations chosen after seeing a hold-out "
        "are labelled hold-out-informed on that hold-out.")
    D.h("26. Leakage prevention and hold-out governance (generated)", 2)
    D.p("Automated leakage checks verify conversation-id disjointness between calibration and evaluation data, that "
        "poison targets are not benign training data, exact-text disjointness between development and evaluation sets "
        "(455 development versus 351 evaluation texts, 0 overlap), and complete poison metadata. Every frozen corpus "
        "below is re-hashed by the benchmark on every run.")
    D.table(holdout_rows(), widths=[5.6, 3.6, 4.2, 3.6], size=8)
    D.p("Hold-out 3 was scored seven times and its development set was found to be the hold-out under a different "
        "wrapper; it was retired and is never scored again. Re-scoring of any held-out split through the benchmark is "
        "counted in every later result (prior_runs_of_this_split).")
    D.h("27. Reproducibility and experimental controls", 2)
    D.p("Temperature 0 with fixed seeds; runs that involve generation are not bit-reproducible because Ollama's "
        "concurrent batching is not deterministic (measured run-to-run SD 0.8–1.7 points), so no difference below the "
        "noise floor 5·√(120/n) points is claimed. Detection and ranking on fixed text are deterministic. Judge and "
        "score caches are keyed and append-only; the benchmark records whether a judge decision came from cache.")

    # PART IV ----------------------------------------------------------------------------
    reg, task_rows, metric_rows = benchmark_rows()
    D.h("Part IV — Unified Benchmark", 1)
    D.h("28. Overview", 2)
    D.p(f"The unified benchmark is the mambench/ package: one registry (registry version {reg['registry_version']}: "
        f"{len(reg['tracks'])} tracks, {len(reg['tasks'])} tasks, {len(reg['metrics'])} metrics), one result schema, one "
        "entry point (python -m mambench). Every task wraps an existing frozen project component. The historical "
        "'8 tracks / 16 tasks / 33 metrics' figure was not found anywhere in the repository and is not reproduced.")
    D.h("29. Architecture", 2)
    D.table([["Module", "Responsibility"],
             ["mambench/registry.json", "tracks, tasks, metrics (numerator and denominator for every proportion), split roles, requirements"],
             ["mambench/registry.py", "registry validation; requirement probes (licensed data, processed corpora, judge caches, Ollama, isolated interpreter)"],
             ["mambench/tasks.py", "one executor per task, wrapping a frozen component; raises NotEvaluable or IntegrityViolation"],
             ["mambench/schema.py", "statuses, metric constructors, result validation, aggregation without an overall score"],
             ["mambench/runner.py", "CLI, execution rules, provenance, hold-out run ledger, tracked-file guard"],
             ["mambench/tests/", "registry, schema and failure-path tests and a real offline smoke run"]], widths=[4.5, 12.5])
    D.h("30. Tracks and tasks (generated)", 2)
    D.table([["Track", "Question"]] + [[k, v] for k, v in reg["tracks"].items()], widths=[4.5, 12.5])
    D.table(task_rows, widths=[5.2, 3.2, 2.6, 3.0, 3.0], size=7.5)
    D.h("31. Canonical specification", 2)
    D.p("docs/phase17/BENCHMARK_SPECIFICATION.md defines scenario, environment, defence and result fields (Sections 1–6) "
        "and the unified runner (Section 7). phase17/bench_runner.py remains the single-split runner the defence tasks call.")
    D.h("32. Task registry and configuration", 2)
    D.p("python -m mambench validate checks that task ids are unique, tracks and split roles exist, every metric is "
        "defined with a numerator and denominator where it is a proportion, every executable task has an executor and "
        "existing implementation files, unsupported tasks state why and have no executor, and every track has a task.")
    D.h("33. Dataset and split organisation", 2)
    D.table([["Split role", "Meaning"]] + [[k, v] for k, v in reg["split_roles"].items()], widths=[4, 13])
    D.h("34. Attack and defence interfaces", 2)
    D.p("Attacks implement phase4/shared/adapter.py::AttackAdapter (validate, prepare, generate, inject are attack-specific; "
        "execute and collect are shared); controlled_campaign.py turns an injected memory and a query into one comparable "
        "record. Defences are dispatched by phase14.defended_retrieval.apply_defense(config, items) over REAL_CONFIGS.")
    D.h("35. Metrics and result schema (generated)", 2)
    D.table(metric_rows, widths=[4.6, 2, 10.4], size=7.5)
    D.p("Each result records task_id, task_version, track, status, reason, split_role, prior_runs_of_this_split, metrics "
        "(metric, group, kind, numerator, denominator, value), details, and provenance (registry and schema version, "
        "config hash, implementation digest over the task's source files, git commit and dirty flag, seed, Python "
        "version, platform, start and finish times).")
    D.h("36. Execution workflow", 2)
    D.numbered(["Select tasks (--task, --track, --smoke, --all).",
                "UNSUPPORTED if the registry marks the task out of scope; BLOCKED if a requirement is unmet. Neither runs.",
                "Otherwise seed, record tracked-file state, run the executor in a scratch directory.",
                "FAILED on an exception, an integrity violation, or any modification of a tracked file; NOT_EVALUABLE when evidence is absent.",
                "Validate the result, append held-out runs to the ledger, write tasks/<id>.json and results.json."])
    D.h("37. Evaluation and aggregation rules", 2)
    D.p("Aggregation lists every registered task with its status (unselected tasks as SKIPPED), counts statuses per track, "
        "and keeps each task's metrics with their denominators. It refuses results from different registry versions or "
        "commits. There is no single MAMBench score. The exit code is non-zero if any task FAILED, and with --strict also "
        "if any is BLOCKED or NOT_EVALUABLE.")
    D.h("38. NOT_EVALUABLE and eligibility rules", 2)
    D.p("A proportion with a zero denominator cannot be constructed; executors raise NotEvaluable instead, and a "
        "NOT_EVALUABLE result may not carry metrics. Integrity-critical tasks (ledger tamper evidence, evaluator-field "
        "rejection, leakage checks, frozen-corpus digests) fail closed.")
    D.h("39. Validation, leakage and determinism checks", 2)
    D.p("mambench/tests (31 tests) cover registry validation failures, schema violations, every runner status, the hold-out "
        "ledger, strict mode, and a real smoke run that must leave tracked files untouched. The LoCoMo-only leakage checks "
        "(licensed-data CI job), the freeze-digest task and the committed-attack-register guard test run in CI.")
    D.h("40. Output structure", 2)
    D.code("mambench_results/<UTC timestamp>-<commit>/results.json\nmambench_results/<UTC timestamp>-<commit>/tasks/<task_id>.json\n"
           "mambench_results/<UTC timestamp>-<commit>/work/<task_id>/\nmambench_results/holdout_ledger.jsonl")
    D.h("41. Adding a task, attack, defence or metric", 2)
    D.numbered(["Metric: add it to registry.json with kind and, for a proportion, numerator and denominator.",
                "Task: add a registry entry (track, split role, requirements, metrics, implementation files) and run_<executor>(params, workdir) in mambench/tasks.py.",
                "Attack: implement AttackAdapter in phase4/attacks/<name>/ and register the population in phase17/attack_register.py.",
                "Defence: add a configuration to phase14/defended_retrieval.py and a task that evaluates it.",
                "Run python -m mambench validate and python -m pytest mambench/tests."])

    # PART V -----------------------------------------------------------------------------
    D.h("Part V — Implementation and Architecture", 1)
    D.h("42. Repository architecture", 2)
    D.table([["Path", "Contents"],
             ["phase3/", "frozen victim agent (V3-Hybrid), memory foundations, dataset candidates, specifications and contracts"],
             ["phase4/", "seven attacks and the shared attack contract"],
             ["phase5/, attribution/", "instrumentation, event ledger, attribution layer"],
             ["phase6/–phase15/", "defences, propagation, sleeper detection, risk composition, GNN/GLN, metrics, utility"],
             ["phase17/", "ablation, generalisation, hold-outs, defence programmes v2–v7, judge caches, run logs"],
             ["mambench/", "unified benchmark"],
             ["preprocessing/, data/metadata/", "Phase 1–2 pipeline; dataset manifests and freeze records"],
             ["docs/, paper/, results/", "phase reports, figures, specifications; manuscript sources; result tables"],
             ["scripts/, .github/workflows/", "utilities and CI checks; the CI workflow"]], widths=[4.5, 12.5])
    D.h("43. Core components", 2)
    D.p("Victim agent (phase3/evaluation), attack adapters (phase4/shared), event and provenance ledgers (phase5, "
        "phase17/defence_v6/ledger.py, phase17/defence_v7/ledger_chain.py), guards (phase6/defense), risk composition "
        "(phase6/defense/risk), learned components (phase11), Consolidation Guard (phase12), attribution (attribution/, "
        "phase13), live configurations (phase14/defended_retrieval.py), Phase 17 evaluation and corpora (phase17/).")
    D.h("44. Data flow", 2)
    D.code("raw datasets → preprocessing (Phases 1–2) → unified memory records → victim agent memory store\n"
           "attack injector → candidate memory → defence (admission → retrieval → consolidation → activation)\n"
           "→ agent answer → judge / counterfactual → result record → Results Analysis tables")
    D.h("45. Key interfaces and dependencies", 2)
    D.p("MemoryFoundationAdapter (phase3), AttackAdapter (phase4), apply_defense (phase14), attribution functions "
        "(attribution/), the signal contract (phase6/defense/signals/contract.py). Python dependencies are listed in "
        "requirements.txt (lower bounds) and pinned for CI in requirements-ci.txt (hashed, Linux, Python 3.11).")
    D.h("46–47. Configuration, models and external services", 2)
    D.table([["Requirement", "Where documented"],
             ["Ollama with qwen2.5:7b, llama2, phi3:mini, mistral, llama3.1:8b, llama-guard3", "phase17/OLLAMA_MODEL_PINS.md"],
             ["Gemini API key (independent judge; optional)", "phase17/gemini_provider.py"],
             ["Isolated Mem0 / A-MEM interpreters (C:\\h4venv, C:\\mem0venv)", "phase17/ISOLATED_ENVIRONMENTS.md"],
             ["Licensed raw data (data/raw/) and processed corpora (data/processed/)", "data/metadata/dataset_manifest.json; DATA_LICENSING_AND_ANNOTATION_AUDIT.md"],
             ["HuggingFace models (all-MiniLM-L6-v2, deberta-v3 prompt-injection, NLI cross-encoder)", "downloaded on first use"]], widths=[9.5, 7.5])
    D.h("48. Error handling and failure behaviour", 2)
    D.p("Benchmark tasks fail closed (section 36). Long runs use atomic checkpoint writes and resume tooling "
        "(phase17/defence_v7/atomic.py, status.py; phase17/RESUME_AFTER_SHUTDOWN.md). The root conftest.py converts two "
        "known external-resource failures into skips and records each one; CI holds their number to a budget.")
    D.h("49. Security considerations", 2)
    D.p("Attacks run only against local, offline infrastructure. Evaluator-only fields are rejected by the risk scorer. "
        "Provenance records are hash-chained (optionally HMAC-keyed). CI runs with read-only permissions, pinned action "
        "commits and no secrets; no live model is reachable from CI.")
    D.h("50. Logging and auditability", 2)
    D.p("Every result carries provenance; the remediation register records every review finding and its status; "
        "phase17/data/error_registry.json records past process errors with a mutation-tested guard for each; "
        "phase17/data/run_all_logs/ holds the run logs and is never modified.")
    D.h("51. Important implementation decisions", 2)
    D.bullets(["Additive phases over frozen code: later phases wrap earlier ones; frozen files are verified unchanged.",
               "One source per number: the Results Analysis and Methodology are generated from artifacts by Python builders.",
               "Caches change by additions only; a cache key mismatch is migrated forward, never silently reused."])

    # PART VI ----------------------------------------------------------------------------
    D.h("Part VI — Results and Evidence", 1)
    D.p("Summary only. The Results Analysis is authoritative for every number below, its denominators and intervals.")
    D.h("52. Evidence collected", 2)
    D.p("Phase reports (docs/phaseN), round-by-round Phase 17 results, eight frozen hold-out corpora plus pre-registered "
        "single-use corpora for the defence programmes (SA-3 to SA-7, HO9, HO10, CSD-7), human annotations of judge "
        "agreement, and the benchmark's own runs.")
    D.h("53. Main findings", 2)
    D.table([["Finding", "Result", "Source"],
             ["Working attacks", "42.5% of 2,628 both work and implement their mechanism (435–944 by probe and judge)", "Results §3, §16–17"],
             ["Provenance on memory-poisoning hold-outs", "B13 vs B14: 50.3% vs 20.4%; 54.3% vs 29.5%; 73.8% vs 43.1% (HO8, p=5e-14)", "Results §13"],
             ["Additive fabrication", "B12 0/72 vs B13 37/72, pre-registered", "Results §4"],
             ["Harm (human-validated judge, 309 items)", "58.3% undefended → 24.6% with B13; task alone 2.3%", "Methodology §32.63"],
             ["Adaptive evasion", "24.6% → 0.8% behind the rejection ledger (p=9.3e-10); blast radius 29.7% at 0.90, 6.4% at 0.95", "Results §9"],
             ["Phase 6 frozen corpus (B8)", "24/34 detected (70.6%) at 3/41 false positives (7.3%), reproduced by mambench", "Methodology §21.9"],
             ["Gap closure (v7)", "Gap 1 75.0%, Gap 2 71.2%, Gap 3 33.8%", "Results §24"]],
            widths=[4, 9.5, 3.5])
    D.figure(ROOT / "docs" / "figures" / "v7" / "W4_closure.png", "Figure 3. Operational closure per research gap.")
    D.h("54. Ablations and comparisons", 2)
    D.p("Phase 17 removed each defence component in turn with Holm-corrected exact McNemar tests against the full stack; "
        "the B0–B8 factorial on the frozen 75-scenario corpus shows the contribution of each guard (B4 18/34, B7 19/34, "
        "B8 24/34 detected; B1, B3 and B6 add no false positives). Native-metadata and two-stage-frame ablations are "
        "reported for Defence v6.")
    D.h("55. Negative results and unsuccessful approaches", 2)
    D.bullets(["Six negative or mixed GNN/GLN results before a composition fix; learned models stay at parity.",
               "Rejection memory: no effect at its frozen radius; the first pre-registered re-run was under-powered.",
               "Neutralisation composed with a cheap detector failed its pre-registered dominance test.",
               "Defence v7: condition E fails its benign limit on SA-7 (19/144 = 13.2%); two new sleeper signals failed development gates; DCR failed its gate before DCR-2.",
               "Retracted: the multi-hop 'reasoning ceiling' (an evaluator artifact) and exfiltration's zero harm as a defect (a generator defect, now fixed)."])
    D.h("56. Generalisation", 2)
    D.p("Detection generalises partly: to novel mechanisms (B12 excludes 42.5–58.3% depending on how 'unseen' is "
        "defined), to Chinese text weakly (37/84 union), and to unseen authors and owners for provenance; union "
        "configurations run at 10.2–11.0% matched-benign false positives on a new injection corpus.")
    D.h("57. Known weaknesses and failure modes", 2)
    D.bullets(["Implicit sleepers: no pre-registered operating point meets the 10% legitimate-rule limit.",
               "User-relayed attacks pass every provenance defence (0/24).",
               "Legitimate rules that arrive through documents or without a recorded source look like planted ones.",
               "The rejection ledger has a ledger-poisoning blast radius and does nothing against single-shot or scope-distributed attackers."])
    D.h("58. Evidence limitations", 2)
    D.p("Agents and judges are 7–8B local models; harm levels depend on the judge, so reductions are more reliable than "
        "levels; human checks rest on two annotators (the owner and the owner's friend) and 100 items; several results "
        "hold at their pre-registered alpha but not after family-wide correction; propagation and sleeper guards are "
        "exercised in constructed settings.")
    D.h("59. Reproducibility status", 2)
    D.p("Offline tasks and cached-judge evaluations reproduce exactly (the benchmark reproduces B7, B8 and the published "
        "held-out split counts). Live runs reproduce within the measured noise floor. Numbers that depend on the "
        "isolated Mem0/A-MEM environments or the processed corpora reproduce only where those exist.")
    D.h("60. Supported claims versus open questions", 2)
    D.table([["Supported by held-out evidence", "Still open"],
             ["Provenance reaches memory poisoning content detection misses", "Implicit sleeper detection within benign limits"],
             ["The ledger reduces adaptive evasion (at a stated cost)", "Activation control after memory rewriting"],
             ["Graded provenance closes Gap 1 to 75% under the rubric", "Lineage deleted after writing (recovery is approximate)"],
             ["No-decay containment withholds 64.3% at generation 4", "User-channel poisoning"]], widths=[8.5, 8.5])

    # PART VII ---------------------------------------------------------------------------
    D.h("Part VII — Reproducibility and Operations", 1)
    D.h("61–62. Installation and dependency management", 2)
    D.code("pip install -r requirements.txt              # development (lower bounds)\n"
           "pip install --require-hashes -r requirements-ci.txt   # exact, hashed (Linux, Python 3.11; what CI installs)")
    D.p("requirements-lock.txt is a freeze of the Windows/CUDA development machine and is not portable.")
    D.h("63–65. Configuration, datasets and models", 2)
    D.p("Licensed data is not committed. LoCoMo can be fetched and verified with python scripts/ci/fetch_licensed_data.py "
        "(pinned upstream commits, sha256 checked against the manifest). The processed unified-memory corpora are built "
        "by preprocessing/run_all.py from raw data; MSC must be obtained from its source by the user. Local models are "
        "pulled with Ollama by the tags in phase17/OLLAMA_MODEL_PINS.md.")
    D.h("66. Running tests", 2)
    D.code("make regression        # Phases 3–16, attribution, tests/, full Phase 17, benchmark checks (what CI runs)\n"
           "python -m pytest mambench/tests -q")
    D.h("67. Running the unified benchmark", 2)
    D.code("python -m mambench validate\npython -m mambench list\npython -m mambench run --smoke --strict\n"
           "python -m mambench run --all\npython -m mambench run --track defence_detection")
    D.h("68. Reproducing experiments", 2)
    D.p("Phase-level experiments have module entry points named in their reports; Phase 17 live stages are listed in the "
        "Makefile (review4-*, review5-pipeline, amem-live, mem0-live) and phase17/RUNNING_THE_PIPELINE.md (one job at a "
        "time; kill orphaned processes between stages). Defence-programme runs resume from checkpoints "
        "(docs/phase17/v7/RESUME_V7.md).")
    D.h("69. Understanding outputs", 2)
    D.p("See section 40 for benchmark outputs. Experiment outputs live under phase17/data/ (JSON per study) and "
        "results/tables/; the Results Analysis' Appendix A indexes every artifact.")
    D.h("70. Troubleshooting", 2)
    D.bullets(["BLOCKED tasks: python -m mambench list shows which requirement is missing.",
               "Slow or hanging live stages: GPU contention from orphaned Python processes (scripts/kill_orphan_phase17.ps1).",
               "Fingerprint test failures on Windows: line endings; .gitattributes pins the fingerprinted raw trees to LF.",
               "Tests skipped with 'auto-skipped (conftest.py)': licensed data or a model download is unavailable."])
    D.h("71. CI/CD behaviour (generated)", 2)
    D.table(ci_rows(), widths=[4, 13])
    D.p("Triggers: pushes to main and remediation/**, pull requests to main, manual dispatch. Permissions are read-only, "
        "actions are pinned to commits, jobs have timeouts, a concurrency group cancels superseded runs, and results and "
        "the resolved dependency list are uploaded as artifacts. OLLAMA_BASE_URL points at a closed port so nothing calls "
        "a live model.")
    D.h("72. Artifact integrity and provenance", 2)
    D.p("Frozen corpora are sha256-verified on every benchmark run; LoCoMo is verified against the manifest when fetched; "
        "the committed attack register is checked against its builder; benchmark results carry an implementation digest "
        "and the git commit.")
    D.h("73. Limitations affecting reproducibility", 2)
    D.bullets(["The full four-check leakage audit needs the processed LongMemEval/MSC/Conversation Chronicles corpora (about 3.6 GB); CI runs the two LoCoMo-only checks.",
               "Live numbers need Ollama, the pinned models and, for Mem0/A-MEM results, the isolated interpreters.",
               "Generation is not bit-reproducible; differences below the noise floor are not claimed."])

    # PART VIII --------------------------------------------------------------------------
    D.h("Part VIII — Research Governance and Release Readiness", 1)
    D.h("74. Research integrity and historical evidence", 2)
    D.p("Historical outputs, frozen baselines, judge caches and run logs are kept unchanged; corrections are dated notes "
        "beside the original text; failed experiments and invalid outputs are kept and labelled. The pre-registrations "
        "(docs/phase17/PREREGISTRATION_*.md, docs/phase17/v7/SA7_PREREGISTRATION.md) and freeze records establish what "
        "was decided before each outcome.")
    D.h("75–76. Data governance, licensing and redistribution (generated)", 2)
    D.table(licence_rows(), widths=[3.6, 3.4, 6, 4], size=7.5)
    D.p("No licence has been applied to the repository's own code and documents; that is the owner's decision. Per-item "
        "decisions and caches that contain LoCoMo or toxic-chat text inherit their non-commercial terms.")
    D.h("77–78. Third-party dependencies and attribution", 2)
    D.p("Python packages are listed with exact versions in requirements-ci.txt; model licences (Apache-2.0 for qwen2.5 and "
        "mistral, the Llama 3.1 Community License for llama3.1 and llama-guard3) are recorded in the licensing audit. "
        "Datasets and models are attributed in Part X.")
    D.h("79. Privacy and security", 2)
    D.p("No new human-subject data was collected beyond two annotators' labels; offensive content exists in some external "
        "hold-outs (in-the-wild jailbreaks). Attack artifacts are reported through responsible disclosure before any "
        "public release, per the Methodology's ethics statement.")
    D.h("80–81. Release readiness and known blockers", 2)
    D.table([["Requirement", "Status"],
             ["Code and data licences chosen", "Open (owner decision)"],
             ["InjecAgent licence verified upstream", "Open"],
             ["Gemini output terms reviewed for generated corpora", "Open"],
             ["Third-party paper extracts (ref_*.txt) reviewed for redistribution", "Open (manual review)"],
             ["CI green on GitHub with the new workflow", "Verified locally on Linux (WSL); first hosted run pending a push"],
             ["Documentation consolidated", "This document; source mapping in the appendix"]], widths=[9, 8])
    D.h("82. Open research questions", 2)
    D.p("Implicit sleeper detection within benign limits; activation control after rewriting; recovery when lineage is "
        "deleted after writing; user-channel poisoning; behaviour with stronger agents and tool-using victims.")

    # PART IX ----------------------------------------------------------------------------
    D.h("Part IX — Limitations and Future Work", 1)
    D.h("83–84. Current limitations and threats to validity", 2)
    D.bullets(["7–8B local agents and judges; judge-dependent harm levels.",
               "Attack reconstructions rather than original code; AgentPoison weaker than published.",
               "Small populations in several defence-programme sub-tests (e.g. 7 factual descendants at generation 4).",
               "Single owner pool exhausted after SA-7; later fresh tests need a new conversation source.",
               "Constructed settings for propagation and sleeper guards."])
    D.h("85–86. Generalisation boundaries and error risks", 2)
    D.p("False positives concentrate on untrusted channels (11.8–15.3% for B13 on matched benign notes, 0% on the user's "
        "own words); false negatives concentrate on user-relayed attacks, implicit sleepers and paraphrased additive "
        "fabrication.")
    D.h("87–89. Unresolved gaps, future directions and deferred work", 2)
    D.p("Gap 3 (implicit sleepers) is the main unresolved gap. Deferred: a powered behavioural sleeper test on a fresh "
        "conversation source, an authenticated-writer memory layer, a powered factual containment set, and a tool-using "
        "victim agent for the four inapplicable MPBench classes. No new phase is opened by this document.")

    # PART X -----------------------------------------------------------------------------
    D.h("Part X — References and Appendices", 1)
    D.h("90. References (generated)", 2)
    meth, rel = references()
    D.p("Verified references from the Methodology Draft (Section 16):", bold_lead=None)
    for r_ in meth:
        d.add_paragraph(r_, style="List Number")
    D.p("Additional works compared in RELATED_WORK_AND_NOVELTY.md (as recorded there; venue as stated on arXiv):")
    for r_ in rel:
        d.add_paragraph(r_, style="List Bullet")
    D.h("91. Glossary", 2)
    D.table([["Term", "Meaning"],
             ["B0–B19", "defence configurations (section 22)"], ["Working attack", "an instance that changes an undefended agent's answer and implements its labelled mechanism"],
             ["Flagged / excluded", "any action other than ALLOW / QUARANTINE or BLOCK"], ["Hold-out (HO)", "a corpus frozen by sha256 before the configurations it tests, scored under pre-registration"],
             ["SA-n", "single-use sleeper/provenance corpora of the defence programmes"], ["GP", "graded provenance (exclude / frame / keep)"],
             ["ND|RAR-S", "no-decay guard or sentence-level fingerprint containment"], ["DCR-2", "lineage recovery after deletion and rewrite"],
             ["Condition E", "pre-registered sleeper operating point (intent judge via a validated semantic link)"],
             ["Closure", "evidence-strength score of a research gap under the frozen rubric"],
             ["BLOCKED / NOT_EVALUABLE / UNSUPPORTED", "benchmark statuses (section 36)"]], widths=[4.5, 12.5])
    D.h("92. Canonical repository structure", 2)
    D.p("See section 42.")
    D.h("93–94. Benchmark configuration and metric definitions", 2)
    D.p("See sections 30, 33 and 35 (generated from mambench/registry.json) and section 24 (generated from phase17/formulas.py).")
    D.h("95. Essential commands", 2)
    D.code("pip install -r requirements.txt\nmake regression\npython -m mambench run --smoke --strict\n"
           "python scripts/ci/fetch_licensed_data.py\npython -m phase17.attack_register\n"
           "python -m phase17.build_results_analysis_docx\npython -m phase17.update_methodology_v7\n"
           "python scripts/build_comprehensive_documentation.py")
    D.h("96. Documentation inventory and source mapping (generated)", 2)
    D.p("Every documentation file was classified before consolidation (docs/cleanup/CLEANUP_INVENTORY.md). Nothing was "
        "deleted or moved by this consolidation.")
    D.table(inventory_counts(), widths=[12, 5])
    D.table([["Source documents", "Destination in this document", "Preserved", "Not copied, and why"],
             ["Methodology Draft (Sections 1–4, 14–16, 33)", "Parts I–III, VIII, X", "objectives, threat model, phases, ethics, references, conclusions", "full method detail stays in the Methodology"],
             ["Results Analysis (Abstract, 2, 10–14, 22–24)", "Part VI", "headline results with denominators and sources", "tables and statistics stay in the Results Analysis"],
             ["README snapshots (docs/history/)", "Parts I, VI", "current state, superseded snapshots noted", "dated snapshots kept verbatim"],
             ["Defence-programme reports (root *_REPORT.md, DEFENCE_V*.md)", "Parts III, VI, IX", "mechanisms, closure, failures", "originals kept as evidence"],
             ["Phase reports (docs/phaseN, phase3/experiments, phase5)", "Part III", "phase roadmap and design decisions", "originals kept; several are read by tests"],
             ["BENCHMARK_SPECIFICATION.md, BENCHMARK_CARD.md", "Part IV", "schema, threat model, runner", "kept as machine-facing specifications"],
             ["DATA_LICENSING_AND_ANNOTATION_AUDIT.md", "Part VIII", "licence table", "kept (legal)"],
             ["RELATED_WORK_AND_NOVELTY.md, NOVELTY_MATRIX.md", "Parts I–II, X", "contribution classes, compared works", "per-capability matrix kept"],
             ["REMEDIATION_MASTER_REGISTER.md", "Parts VIII–IX", "open items and statuses", "kept (live register)"],
             ["Operational guides (phase17/*.md)", "Part VII", "commands and requirements", "kept beside the code"]],
            widths=[4.6, 3.2, 4.6, 4.6], size=7.5)
    D.h("97. Known limitations and release blockers", 2)
    D.p("See sections 73, 80–81 and 83–89.")
    D.save(OUT)
    return OUT


if __name__ == "__main__":
    print(build())
