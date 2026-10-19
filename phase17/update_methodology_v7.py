"""Bring `Methodology Draft.docx` up to date with Defence v7 (2026-10-15/17). Idempotent: the block sits between its own
start and end markers, after the v6 block (Section 32.71) and before Section 33; a re-run replaces only this block.
A v7 conclusion status paragraph is placed after the v6 one (which gains a 'superseded' pointer), and the 2026-10-14
closure caption gains a qualifier. Content comes from phase17/results_sections_v7.py (the same generator as the Results
Analysis), so the two documents cannot disagree. Log: remediation/logs/methodology_update_v7.json.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "Methodology Draft.docx"
LOG = ROOT / "remediation" / "logs" / "methodology_update_v7.json"
MARK = "[Section 32.72: Defence Programme v7 (2026-10-15/17), generated from the v7 artifacts.]"
END_MARK = "[End of the Defence v7 update.]"
STATUS7 = "[Status 2026-10-17, Defence v7]"
STATUS6 = "[Status 2026-10-15, Defence v6]"
V6_POINTER = " [Superseded by the 2026-10-17 status below.]"
OLD_CAP = "no gap reaches 75%."
NEW_CAP = ("no gap reaches 75% (scores as of 2026-10-14; superseded by Sections 32.71 and 32.72: after Defence v7, Gap 1 "
           "reaches 75%).")


def _text(el):
    return "".join(t.text or "" for t in el.iter() if t.tag.endswith("}t"))


def _content(printed=frozenset()):
    """printed = formula names already present in the Methodology's other formula tables (outside this block)."""
    from phase17.formulas import rows as formula_rows
    from phase17.results_sections_v7 import blocks

    out = [("p", MARK)]
    out.append(("p", "Methods summary. v7 kept the frozen closure rubric and wrote one pre-registration for all three gaps "
                     "before any v7 data existed (addenda A-C recorded with checksums before the outcomes they concern); "
                     "development choices used development owners or roots only; every held-out set was frozen by digest and "
                     "scored once after the development selections were frozen; defects are kept as *_INVALID_* outputs."))
    for kind, x in blocks(doc="methodology"):
        if kind == "h":
            out.append(("h2", "32.72 " + x.split(". ", 1)[1]))
        elif kind == "h2":
            out.append(("h3", "32.72." + x.split(" ", 1)[0].split(".", 1)[1] + " " + x.split(" ", 1)[1]))
        elif kind == "cap":
            out.append(("cap", x.replace("Table 24.", "Table 32.72.")))
        elif kind == "p" and not x:
            continue
        else:
            out.append((kind, x))
    fr = formula_rows()
    start = next(i for i, r in enumerate(fr) if r[0] == "Graded provenance (GP, v7)")
    out.append(("table", [fr[0]] + fr[start:]))
    out.append(("cap", "Table 32.72.F. Formulas added by Defence v7 (the full set is in the Results Analysis, 'Definitions and "
                       "Formulas')."))
    v7 = {r[0] for r in fr[start:]}
    earlier = [r for r in fr[1:] if r[1] and r[0] not in printed and r[0] not in v7]
    if earlier:
        out.append(("table", [fr[0]] + earlier))
        out.append(("cap", "Table 32.72.G. Formulas defined before v7 but not printed in Sections 32.62-32.71 (completes the "
                           "Methodology's set: with Tables 32.62, 32.70, 32.71.F and 32.72.F every formula is printed)."))
    out.append(("p", END_MARK))
    return out


STATUS7_CURRENT = "After Defence v7 (Section 32.72) the evidence-based operational closure"


def _status_text():
    """Current-state closure line for Section 33 (2026-10-19: no dated '[Status ...]' label)."""
    c = json.loads((ROOT / "phase17" / "data" / "defence_v7" / "closure_v7.json").read_text(encoding="utf-8"))
    g = list(c["gaps"].items())
    now = "; ".join(f"{k.split(': ')[-1]} {v['after_v7'] * 100:.0f}%" for k, v in g)
    before = ", ".join(f"{v['before_v6'] * 100:.0f}%" for _, v in g[:-1]) + f" and {g[-1][1]['before_v6'] * 100:.0f}%"
    return (f"{STATUS7_CURRENT} under the frozen rubric is: {now} ({before} after Defence v6). Gap 1 reaches 75% through "
            "graded provenance on fresh held-out data; Gap 2 rises through no-decay containment and lineage recovery after "
            "rewriting, with its factual sub-test read strictly; Gap 3 is unchanged because the pre-registered sleeper "
            "operating point exceeds the legitimate-rule limit.")


GUIDE_OLD = "The current state of the project is Sections 32.49-32.63 (round 7) and Section 33;"
GUIDE_NEW = ("The current state of the project is Sections 32.64-32.72 (the 2026-10-12 remediation and the pre-registered "
             "defence programmes v2-v7) and the dated status lines at the end of Section 33 [updated 2026-10-17; round 7 "
             "is Sections 32.49-32.63];")
STATUS14 = "[Status 2026-10-14]"
S14_POINTER = " [Superseded by the 2026-10-15 and 2026-10-17 status lines below.]"
CAPTION_FIXES = [  # (old caption tail, new caption tail) for the 2026-10-14 figures, whose generator is not re-run
    ("The evaluated defence architecture and each component's status.",
     "The evaluated defence architecture and each component's status (as of 2026-10-14; superseded by Sections 32.71 and 32.72)."),
    ("Operational closure per research gap.",
     "Operational closure per research gap (as of 2026-10-14; superseded by Sections 32.71 and 32.72)."),
]
FIG1B_HEADING = "Figure 1b — Overall Pipeline, continued"
STALE_MON_NOTE = (" [Status as of round 7: the first surface (risk band -> action) was wired into the live defended agent by "
                  "Phase 14 as configuration B9 (Section 29). The risk-weighted retrieval ranking was evaluated for the first "
                  "time in round 7 (Section 32.61): poison exposure 88 -> 82 of 309 against the fixed gate when admission "
                  "signals corroborate (p=0.031), at no benign displacement. Risk-weighted monitoring remains built and "
                  "tested but not evaluated.]")


def _set_par_text(p, t):
    for r in p.runs[1:]:
        r._r.getparent().remove(r._r)
    if p.runs:
        p.runs[0].text = t
    else:
        p.add_run(t)


def _in_place_fixes(doc) -> dict:
    """Idempotent fixes to paragraphs no generator rebuilds; each counts 'applied' or 'already'."""
    from docx.oxml.ns import qn

    out = {}
    g = next((p for p in doc.paragraphs if GUIDE_OLD in p.text), None)
    out["reading_guide"] = "applied" if g is not None else ("already" if any(GUIDE_NEW in p.text for p in doc.paragraphs) else "missing")
    if g is not None:
        _set_par_text(g, g.text.replace(GUIDE_OLD, GUIDE_NEW))
    s14 = next((p for p in doc.paragraphs if p.text.startswith(STATUS14)), None)
    if s14 is not None and not s14.text.endswith(S14_POINTER):
        s14.add_run(S14_POINTER)
        out["status_2026_10_14"] = "applied"
    else:
        out["status_2026_10_14"] = "already" if s14 is not None else "missing"
    for old, new in CAPTION_FIXES:
        hits = [p for p in doc.paragraphs if p.text.endswith(old)]
        for p in hits:
            _set_par_text(p, p.text[: -len(old)] + new)
        out[old[:30]] = f"applied {len(hits)}" if hits else ("already" if any(p.text.endswith(new) for p in doc.paragraphs) else "missing")
    # Section 25.2 carried the round-7 status note twice; the second copy predates the monitoring evaluation
    dup = [p for p in doc.paragraphs if STALE_MON_NOTE in p.text]
    for p in dup:
        _set_par_text(p, p.text.replace(STALE_MON_NOTE, ""))
    out["stale_monitoring_note"] = f"applied {len(dup)}" if dup else "already"
    # Figure 1b: swap the embedded image for the redrawn one (withdrawn union claim removed; defence programmes added)
    from phase17.figures_round7 import fig01b

    png = fig01b()
    ps = doc.paragraphs
    i = next((k for k, q in enumerate(ps) if q.text.startswith(FIG1B_HEADING)), None)
    out["figure_1b"] = "missing"
    if i is not None:
        for q in ps[i:i + 4]:
            blip = q._p.find(".//" + qn("a:blip"))
            if blip is None:
                continue
            part = doc.part.related_parts[blip.get(qn("r:embed"))]
            new = png.read_bytes()
            if part.blob == new:
                out["figure_1b"] = "already"
            else:
                part._blob = new
                from PIL import Image
                w, h = Image.open(png).size
                for ext in q._p.iter(qn("wp:extent")):
                    cx = int(ext.get("cx"))
                    ext.set("cy", str(int(cx * h / w)))
                for ext in q._p.iter(qn("a:ext")):
                    if ext.get("cx"):
                        cx = int(ext.get("cx"))
                        ext.set("cy", str(int(cx * h / w)))
                out["figure_1b"] = "applied"
            break
    return out


def run() -> dict:
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.shared import Inches
    from docx.text.paragraph import Paragraph

    from phase17.figures_v7 import run as draw

    figs = {k: ROOT / v for k, v in draw().items() if v}
    doc = Document(str(DOC))
    log = {"removed_previous_block": 0, "inserted": 0, "figures": 0}
    pars = doc.paragraphs
    anchor = next(p for p in pars if p.style.name.startswith("Heading 1") and p.text.startswith("33. Overall Conclusion"))
    body = anchor._p.getparent()
    start = next((p for p in pars if p.text == MARK), None)
    if start is not None:
        el = start._p
        while el is not None and el is not anchor._p:
            nxt = el.getnext()
            is_end = el.tag.endswith("}p") and _text(el) == END_MARK
            body.remove(el)
            log["removed_previous_block"] += 1
            el = nxt
            if is_end:
                break
        ins_el = el if el is not None else anchor._p
    else:
        v6_end = next((p for p in doc.paragraphs if p.text == "[End of the Defence v6 update.]"), None)
        ins_el = v6_end._p.getnext() if v6_end is not None else anchor._p
    ins = Paragraph(ins_el, anchor._parent) if ins_el.tag.endswith("}p") else None
    import re

    nums = [int(m.group(1)) for p in doc.paragraphs for m in [re.match(r"Figure (\d+) - ", p.text)] if m]
    fig_no, prev = (max(nums) if nums else 0), None
    styles = {s.name for s in doc.styles}

    def before(text=None, style=None):
        if ins is not None:
            return ins.insert_paragraph_before(text, style=style) if text is not None else ins.insert_paragraph_before()
        el = OxmlElement("w:p")
        ins_el.addprevious(el)
        par = Paragraph(el, anchor._parent)
        if text is not None:
            par.add_run(text)
        if style:
            par.style = style
        return par

    printed = set()
    for t in doc.tables:
        hdr = [c.text for c in t.rows[0].cells]
        if hdr[:2] == ["Quantity", "Formula"]:
            printed |= {r.cells[0].text for r in t.rows[1:] if r.cells[1].text}
    log["formula_tables_completed_with"] = 0
    content = _content(frozenset(printed))
    log["formula_tables_completed_with"] = sum(len(x) - 1 for k, x in content if k == "table" and x and x[0][0] == "Quantity") 
    for kind, payload in content:
        if kind == "cap" and prev == "fig":
            fig_no += 1
            payload = f"Figure {fig_no} - {payload}"
        if kind == "fig":
            path = figs.get(payload)
            prev = "fig" if path and path.exists() else "nofig"
            if prev == "fig":
                before().add_run().add_picture(str(path), width=Inches(6.3))
                log["figures"] += 1
            continue
        if kind == "cap" and prev == "nofig":
            prev = kind
            continue
        prev = kind
        if kind == "h2":
            before(payload, "Heading 2")
        elif kind == "h3":
            before(payload, "Heading 3" if "Heading 3" in styles else "Heading 2")
        elif kind in ("p", "cap"):
            before(payload)
        elif kind == "table":
            t = doc.add_table(rows=len(payload), cols=len(payload[0]))
            try:
                t.style = "Table Grid"
            except Exception:  # noqa: BLE001
                pass
            for i, row in enumerate(payload):
                for j, v in enumerate(row):
                    t.cell(i, j).text = str(v)
            ins_el.addprevious(t._tbl)
        log["inserted"] += 1

    # conclusion status: v7 paragraph after the v6 one (replaced in place on re-runs); v6 gains a pointer
    txt = _status_text()
    ex7 = next((p for p in doc.paragraphs if p.text.startswith((STATUS7, STATUS7_CURRENT))), None)
    ex6 = next((p for p in doc.paragraphs if p.text.startswith(STATUS6)), None)
    if ex6 is not None and not ex6.text.endswith(V6_POINTER):
        ex6.add_run(V6_POINTER)
    if ex7 is not None:
        for r in ex7.runs[1:]:
            r._r.getparent().remove(r._r)
        ex7.runs[0].text = txt
    elif ex6 is not None:
        el = OxmlElement("w:p")
        ex6._p.addnext(el)
        Paragraph(el, ex6._parent).add_run(txt)
    else:
        anchor.insert_paragraph_before(txt)
    log["status"] = txt[:200]

    # qualify the superseded 2026-10-14 closure caption (idempotent)
    cap = [p for p in doc.paragraphs if p.text.endswith(OLD_CAP) and "Operational gap closure" in p.text]
    for p in cap:
        t = p.text[: -len(OLD_CAP)] + NEW_CAP
        for r in p.runs[1:]:
            r._r.getparent().remove(r._r)
        p.runs[0].text = t
    log["qualified_captions"] = len(cap)
    log["in_place"] = _in_place_fixes(doc)
    from phase17.editorial_pass import apply_to
    log["editorial"] = apply_to(doc, "methodology")      # professional-prose edits, numbers verified; run last
    doc.save(str(DOC))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
    return log


if __name__ == "__main__":
    print(run())
