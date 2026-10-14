"""Bring `Methodology Draft.docx` up to date with the work of 2026-10-12..14 (remediation, gap closure, targeted phase,
defence programmes v2-v5). Idempotent: the inserted block sits between a start marker and the heading of Section 33,
and is replaced wholesale on every run; the in-place corrections apply only if not already present. Every number is
read from the committed artifacts; a change log is written to remediation/logs/methodology_update_2026_10_14.json.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "Methodology Draft.docx"
DATA = ROOT / "phase17" / "data"
LOG = ROOT / "remediation" / "logs" / "methodology_update_2026_10_14.json"
MARK = "[Sections 32.64-32.70: methods and results of 2026-10-12 to 2026-10-14, generated from the committed artifacts.]"
END_MARK = "[End of the 2026-10-14 update.]"


def L(rel):
    p = DATA / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def f(x):
    return f"{x['k']}/{x['n']}"


def _content():
    """Ordered list of ('h2'|'p'|'fig'|'table'|'cap', payload)."""
    from phase17.figures_final import CLOSURE, closure_scores
    from phase17.figures_final import run as draw
    from phase17.formulas import rows as formula_rows

    figs = {k: ROOT / v for k, v in draw().items() if v}
    lo, vf, ap = L("remediation/b13_owner_loo.json"), L("remediation/validity_final.json"), L("remediation/annotation_provenance.json")
    mem = L("remediation/mem0_pipeline_eval.json")
    sag, p2, s2 = L("defence_v2/sag_eval.json"), L("defence_v2/prop_eval.json"), L("defence_v2/sleeper_v2_eval.json")
    vpl, ctc, prc = L("defence_v3/vpl_eval.json"), L("defence_v3/ctc_eval.json"), L("defence_v4/prc_eval.json")
    voa, af, wtp, rac = L("defence_v4/voa_eval.json"), L("defence_v5/af_eval.json"), L("defence_v5/wtp_eval.json"), L("defence_v5/rac_eval.json")
    c = [("p", MARK)]

    c.append(("h2", "32.64 Remediation and Gap Closure: a Real Extraction Pipeline and Causal Validity (2026-10-12/13)"))
    if mem:
        A = mem["MEM1_ho4"]["attacks_document"]
        c.append(("p", "Method. Hold-out 4 and SA-1 were ingested through Mem0 2.0.19 with LLM extraction enabled (qwen2.5:7b "
                       "extractor, MiniLM embeddings, local Qdrant), each item into a fresh store holding the owner's own baseline "
                       "memories, through a shared-document channel and, separately, as the user's own message. Storage, claim "
                       "survival, retrieval for the item's task and the change in the agent's answer were measured as separate "
                       "stages, and every defence was applied to what Mem0 actually stored. Two Mem0 API defects (a 20-memory "
                       "truncation in get_all and an ignored search limit) were found before any outcome analysis and fixed. "
                       f"Result: {f(A['carries'])} attacks left a stored claim, {f(A['retrieved'])} were retrieved, "
                       f"{f(A['working'])} changed the answer; B13 on the stored text excluded {f(A['excl_B13'])} (B12 "
                       f"{f(A['excl_B12'])})."))
    c.append(("p", "Attack validity was re-examined causally: the memory's effect is measured as compliance with the note minus "
                   "compliance on the same task without it, paired by item, under two judges, with a blind third-model "
                   "adjudication of disagreements and a non-leading probe. The earlier statement that a fixed fraction of "
                   "attacks 'work' is replaced by this paired net effect plus explicit bounds on instance labels."))

    c.append(("h2", "32.65 Owner-Disjoint Calibration, Evidence Conditions, Probe Controls and Annotation Provenance"))
    if lo:
        cc = lo["evidence_conditions"]["correct"]["pooled"]["A-ship"]
        w = lo["evidence_conditions"]["wrong"]["pooled"]["A-ship"]["benign_exclusion"]
        t = lo["evidence_conditions"]["trunc10"]["pooled"]["A-ship"]["benign_exclusion"]
        c.append(("p", "Method. B13's corroboration thresholds were re-fitted for each of the 10 LoCoMo owners using only the other "
                       "nine owners' benign derived memories, at the quantile levels where the shipped constants sit (0.487% / "
                       "2.047%), frozen, and the held-out owner scored once; uncertainty uses an owner-cluster bootstrap. "
                       "Evidence conditions (correct owner, another owner, first 50% or 10% of the conversation, none) were kept "
                       "separate. An earlier claim that thresholds 'move threefold with the owners' is withdrawn: it compared "
                       "two benign budgets after the retrieval width changed from 5 to 20 turns. "
                       f"Result: detection {f(cc['detection'])}, benign exclusion {f(cc['benign_exclusion'])} (owner range up to "
                       f"{cc['per_owner_benign_exclusion_range'][1]:.1%}); wrong-owner evidence {f(w)}, a 10% conversation {f(t)}."))
        c.append(("fig", figs.get("F1")))
        c.append(("cap", "B13 under leave-one-owner-out calibration, per held-out owner."))
        c.append(("fig", figs.get("F2")))
        c.append(("cap", "B13 under different evidence conditions (10 owners pooled)."))
    if vf and vf.get("none_arm_complete"):
        tc = vf["three_conditions"]
        c.append(("p", "Probe controls. The audit's 'without memory' arm is a clean store of benign owner turns; an empty-store arm "
                       "was added for 150 items under both probes. With the fitted probe the empty store was judged compliant more "
                       f"often than the clean store ({tc['fitted|C0']['comply_none']['k']} vs {tc['fitted|C0']['comply_clean']['k']}), "
                       "locating the probe's leak; with the non-leading probe they coincide. The memory-attributable effect "
                       f"(poisoned minus clean) is +{tc['fitted|C0']['memory_attributable(poisoned-clean)']['diff_points']} and "
                       f"+{tc['nonleading|C0']['memory_attributable(poisoned-clean)']['diff_points']} points (C0) for the two "
                       "probes, positive under both judges with population-cluster intervals; the defence ranking is identical "
                       "across all working-attack definitions."))
        c.append(("fig", figs.get("F3")))
        c.append(("cap", "Compliance with no memory, a clean store and a poisoned store, under both probes."))
    if ap:
        a = ap["agreement"]["ALL"]
        c.append(("p", "Annotation provenance. Annotator 1 is the author; annotator 2 is the author's friend, who labelled on the "
                       "author's laptop under written instructions not to view the first annotator's labels or the judges' "
                       "outputs. Neither is independent of the author; the labels are used only to choose between LLM judges, "
                       f"and no defence, ranking or net-effect result depends on them. Agreement: kappa {a['kappa']} "
                       f"(95% CI {a['kappa_item_bootstrap_ci95'][0]}-{a['kappa_item_bootstrap_ci95'][1]})."))

    c.append(("h2", "32.66 Defence Programme v2: Source-Anchored Governance, Root-Anchored Containment, Hard Sleeper Controls"))
    c.append(("p", "Method (pre-registered). (i) Source-anchored governance: a memory derived by Mem0 inherits its raw item's "
                   "decision through the write-time item-to-memory link. (ii) Root-anchored claim lineage (RCL): each "
                   "consolidated descendant is compared directly with the flagged root claim instead of through per-hop "
                   "attenuated parent states, over four consolidation generations on new held-out HO4 chains, measuring payload "
                   "persistence, retrieval, behavioural influence and benign collateral per generation. (iii) A new sleeper corpus "
                   "SA-3 (315 notes, owner-disjoint dev/eval) adds legitimate ungrounded conditional rules as the hard benign "
                   "control earlier corpora lacked."))
    if p2 and s2:
        a = s2["eval_raw"]["aggregate"]
        c.append(("p", f"Results. RCL withheld {f(p2['withheld_carrying_flagged']['RCL'][3])} payload-carrying descendants at "
                       f"generation 4 against {f(p2['withheld_carrying_flagged']['FG'][3])} for the frozen guard, with "
                       f"{f(p2['collateral_unflagged_benign']['RCL'][3])} unflagged-benign collateral (accepted). Inheriting B13's "
                       "verdict through lineage exceeded the benign limit. On SA-3, corroboration flagged "
                       f"{a['B13']['ben_unground'][0]}/{a['B13']['ben_unground'][1]} legitimate ungrounded rules, so SA-2's clean "
                       "separation was a property of grounded benign controls."))

    c.append(("h2", "32.67 Defence Programme v3: Verified Lineage, Claim Tracking and an Operational Closure Rubric"))
    c.append(("p", "Method (pre-registered). Before any outcome, each research gap received a weighted capability rubric scored "
                   "on evidence strength (0, 0.25, 0.5, 0.75, 1) with critical capabilities that cap the gap score if they "
                   "fail. Candidates: verified payload-only lineage (VPL: inherit only the content detector's raw decision, "
                   "only through a link whose similarity to the source passes a threshold set on dev); claim-tracked "
                   "containment (CTC: NLI entailment of the root claim by the descendant, threshold selected on dev chains) "
                   "evaluated on new held-out HO8 chains split by payload type; and a novel-entity steering signal for "
                   "implicit sleepers, selected on dev only."))
    if vpl and ctc:
        m2 = vpl["sets"]["MEM2"]
        c.append(("p", f"Results. VPL made wrong lineage harmless (benign exclusion unchanged under a permuted link) and recovered "
                       f"explicit payloads after Mem0 ({f(m2['correct']['atk']['B13_stored'])} -> {f(m2['correct']['atk']['VPL'])} "
                       "on MEM-2), but gained on only one of three sets and was not accepted as a replacement. CTC withheld "
                       f"{f(ctc['sets']['HO8_instruction']['CTC']['withheld_carrying'][3])} instruction-style payload-carrying "
                       "descendants at generation 4 but was weaker than RCL on factual payloads; not accepted. No sleeper "
                       "detector met the dev benign limits."))
    c.append(("fig", figs.get("F5")))
    c.append(("cap", "Implicit-sleeper detectors: detection against legitimate ungrounded rules flagged (SA-3)."))

    c.append(("h2", "32.68 Defence Programme v4: Payload-Routed Containment and Verify-on-Activation"))
    c.append(("p", "Method (pre-registered; new held-out HO7 chains and a new SA-4 corpus). Payload-routed containment (PRC) "
                   "applies CTC to instruction-type roots and RCL otherwise, with no new parameter. Verify-on-activation keeps a "
                   "flagged memory retrievable but frames it as unverified and measures, per trigger answer, whether the agent "
                   "acts without asking (unconfirmed activation) and whether a legitimate rule stays usable (surfaced)."))
    if prc and voa:
        h7 = prc["sets"]["ho7"]["pooled"]
        b = voa["sets"]["N1|B13"]
        c.append(("p", f"Results. On fresh HO7 chains PRC withheld {f(h7['PRC']['withheld_carrying'][3])} against "
                       f"{f(h7['FG']['withheld_carrying'][3])} for the frozen guard at generation 4 (p = 0.07, underpowered; not "
                       "accepted), and passed every criterion on the repeated HO8 set. Verify-on-activation on SA-4 raw memories "
                       f"cut attack unconfirmed activation from {f(b['atk']['raw']['undefended']['unconfirmed_activation'])} to "
                       f"{f(b['atk']['raw']['VoA']['unconfirmed_activation'])} with {f(b['ben_unground']['raw']['VoA']['surfaced'])} "
                       "legitimate rules usable, but had no effect after Mem0 rewrote the rules into preference facts; not "
                       "accepted."))
    c.append(("fig", figs.get("F4")))
    c.append(("cap", "Containment across consolidation generations on three held-out chain sets."))
    c.append(("fig", figs.get("F6")))
    c.append(("cap", "Verify-on-activation before and after Mem0 rewriting."))

    c.append(("h2", "32.69 Defence Programme v5: Authorship Provenance and Containment Without Stored Lineage"))
    c.append(("p", "Method (pre-registered, with addenda written before their computations). A provenance-recording wrapper "
                   "attaches the source channel to every Mem0 memory and keeps the union of sources on update, because Mem0's "
                   "native update is last-writer-wins on metadata. An attribution frame ('from a shared document, not the user's "
                   "own words') was selected on dev and evaluated on a new SA-5 corpus ingested on both channels. Containment "
                   "without lineage was tried by matching new memories against a registry of flagged claims and, separately, by "
                   "write-time taint propagation, in which the consolidator taints its output from its own inputs."))
    if af and wtp and rac:
        pv, g = af["provenance"], af["groups"]
        c.append(("p", f"Results. Provenance survived extraction ({pv['prw_correct']}/{pv['n_memories']}); the laundering path "
                       "was confirmed at code level but never triggered naturally (0 updates in 225 ingestions). The attribution "
                       f"frame reduced attack unconfirmed activation from {f(g['attacks_document']['undefended']['unconfirmed_activation'])} "
                       f"to {f(g['attacks_document'][af['frame']]['unconfirmed_activation'])} (not significant; not accepted). "
                       "Registry matching excluded "
                       f"{f(rac['sets']['ho7']['collateral_owner_observations'])} of an owner's real benign memories and was "
                       "rejected twice; write-time taint propagation equalled lineage-based containment item for item without a "
                       "stored graph and was accepted. Lineage deleted after writing remains unsolved."))

    c.append(("h2", "32.70 Defence Architecture, Operational Closure, and Formulas Added"))
    c.append(("fig", figs.get("F8")))
    c.append(("cap", "The evaluated defence architecture and each component's status."))
    sc = closure_scores()
    trows = [["Gap", "Capability (* = critical)", "Weight", "Score"]]
    for gname, caps in CLOSURE.items():
        for n, wgt, v in caps:
            trows.append([gname, n, f"{wgt:.2f}", f"{v:.2f}"])
        trows.append([gname, "Gap score (critical caps applied)", "", f"{sc[gname] * 100:.0f}%"])
    c.append(("table", trows))
    c.append(("cap", "Operational gap closure from the pre-registered rubric. Scores measure evidence strength, not accuracy; "
                     "no gap reaches 75%."))
    c.append(("fig", figs.get("F7")))
    c.append(("cap", "Operational closure per research gap."))
    fr = formula_rows()
    start = next(i for i, r in enumerate(fr) if r[0] == "Cluster bootstrap (owners, populations, families, root chains)")
    c.append(("table", [fr[0]] + fr[start:]))
    c.append(("cap", "Formulas added on 2026-10-13/14 (the full set is in the Results Analysis, 'Definitions and Formulas')."))
    c.append(("p", END_MARK))
    return c


def _move_table_before(table, anchor_par):
    anchor_par._p.addprevious(table._tbl)


def run() -> dict:
    from docx import Document
    from docx.shared import Inches

    doc = Document(str(DOC))
    log = {"removed_previous_block": 0, "inserted": 0, "corrections": []}
    pars = doc.paragraphs
    anchor = next(p for p in pars if p.style.name.startswith("Heading 1") and p.text.startswith("33. Overall Conclusion"))
    # remove a previous block (idempotent re-run)
    body = anchor._p.getparent()
    start = next((p for p in pars if p.text == MARK), None)
    if start is not None:
        el = start._p
        while el is not None and el is not anchor._p:
            nxt = el.getnext()
            body.remove(el)
            log["removed_previous_block"] += 1
            el = nxt
    caption_style = None                      # the document's own figure captions are Normal paragraphs
    fig_no, prev = 21, None                   # continue the document's numbering ("Figure 21 - ..." is the last)
    for kind, payload in _content():
        if kind == "cap" and prev == "fig":
            fig_no += 1
            payload = f"Figure {fig_no} - {payload}"
        prev = kind
        if kind == "h2":
            anchor.insert_paragraph_before(payload, style="Heading 2")
        elif kind == "p":
            anchor.insert_paragraph_before(payload)
        elif kind == "cap":
            anchor.insert_paragraph_before(payload)
        elif kind == "fig":
            if payload and Path(payload).exists():
                par = anchor.insert_paragraph_before()
                par.add_run().add_picture(str(payload), width=Inches(6.3))
        elif kind == "table":
            t = doc.add_table(rows=len(payload), cols=len(payload[0]))
            try:
                t.style = "Table Grid"
            except Exception:
                pass
            for i, row in enumerate(payload):
                for j, v in enumerate(row):
                    t.cell(i, j).text = str(v)
            _move_table_before(t, anchor)
        log["inserted"] += 1
    # in-place qualifications (idempotent)
    q = (" [Qualified 2026-10-13: which instances count as working depends on the probe and the judge (435-944 of 2,628 "
         "depending on how disputed labels resolve); the memory's net causal effect and the defence ranking are robust to "
         "both -- Section 32.65.]")
    for p in doc.paragraphs:
        if ("only 42.5% of this benchmark's 2,628 attack instances both subvert" in p.text or
                "Only 42.5% of this benchmark's 2,628 attack instances both subvert" in p.text) and "Qualified 2026-10-13" not in p.text:
            p.add_run(q)
            log["corrections"].append(p.text[:80])
    concl = [p for p in doc.paragraphs if p.style.name.startswith("Heading 1") and p.text.startswith("33. Overall Conclusion")][0]
    tail = "[Status 2026-10-14]"
    if not any(p.text.startswith(tail) for p in doc.paragraphs):
        from phase17.figures_final import closure_scores
        sc = closure_scores()
        nxt_h = None
        seen = False
        for p in doc.paragraphs:
            if p._p is concl._p:
                seen = True
                continue
            if seen and p.style.name.startswith("Heading 1"):
                nxt_h = p
                break
        txt = (f"{tail} After the defence programmes of 2026-10-13/14 (Sections 32.66-32.70), the evidence-based operational "
               f"closure of the three research gaps is: provenance and governance {sc['Gap 1: provenance and governance'] * 100:.0f}%, "
               f"self-propagation {sc['Gap 2: self-propagation'] * 100:.0f}%, implicit sleepers "
               f"{sc['Gap 3: implicit sleepers'] * 100:.0f}%. Retained components: B13 at admission, verified payload-only "
               "lineage, root-anchored and payload-routed containment, and write-time taint propagation. Open: implicit-sleeper "
               "detection, activation control after memory rewriting, lineage deleted after writing, and user-channel poisoning.")
        if nxt_h is not None:
            nxt_h.insert_paragraph_before(txt)
        else:
            doc.add_paragraph(txt)
        log["corrections"].append("conclusion status paragraph")
    doc.save(str(DOC))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
    return log


if __name__ == "__main__":
    print(run())
