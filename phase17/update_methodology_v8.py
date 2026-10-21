"""Bring `Methodology Draft.docx` up to date with Defence Programme v8 (2026-10-20/21). Idempotent: the
block sits between its own start and end markers, after the v7 block (Section 32.72) and before Section
33; a re-run replaces only this block. A v8 conclusion status paragraph is placed after the v7 one (which
gains a 'superseded' pointer). Content comes from phase17/results_sections_v8.py (the same generator as
the Results Analysis), so the two documents cannot disagree.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "Methodology Draft.docx"
LOG = ROOT / "remediation" / "logs" / "methodology_update_v8.json"
MARK = "[Section 32.73: Defence Programme v8 (2026-10-20/21), generated from the v8 artifacts.]"
END_MARK = "[End of the Defence v8 update.]"
STATUS8 = "[Status 2026-10-21, Defence v8]"
STATUS7_CURRENT = "After Defence v7 (Section 32.72) the evidence-based operational closure"
V7_POINTER = " [Superseded by the 2026-10-21 status below.]"


def _text(el):
    return "".join(t.text or "" for t in el.iter() if t.tag.endswith("}t"))


def _content(printed=frozenset()):
    from phase17.formulas import rows as formula_rows
    from phase17.results_sections_v8 import blocks

    out = [("p", MARK)]
    out.append(("p", "Methods summary. v8 kept the frozen closure rubric and wrote one pre-registration plus four "
                     "checksummed addenda (W1b, W1b-2, W2, W3), each recorded before the outcome it concerns, on a "
                     "branch isolated from Defence v7 (phase17/tests/test_v7_frozen.py verified v7 unchanged at "
                     "every checkpoint). Development choices used development owners or roots only; every held-out "
                     "set was frozen by digest and scored once after the development selections were frozen; "
                     "deviations are logged and resolved before the outcome they concern was known."))
    for kind, x in blocks(doc="methodology"):
        if kind == "h":
            out.append(("h2", "32.73 " + x.split(". ", 1)[1]))
        elif kind == "h2":
            out.append(("h3", "32.73." + x.split(" ", 1)[0].split(".", 1)[1] + " " + x.split(" ", 1)[1]))
        elif kind == "cap":
            out.append(("cap", x.replace("Table 25.", "Table 32.73.")))
        elif kind == "p" and not x:
            continue
        else:
            out.append((kind, x))
    fr = formula_rows()
    start = next(i for i, r in enumerate(fr) if r[0] == "Authenticated writer signature (v8)")
    out.append(("table", [fr[0]] + fr[start:]))
    out.append(("cap", "Table 32.73.F. Formulas added by Defence v8 (the full set is in the Results Analysis, "
                       "'Definitions and Formulas')."))
    v8 = {r[0] for r in fr[start:]}
    earlier = [r for r in fr[1:] if r[1] and r[0] not in printed and r[0] not in v8]
    if earlier:
        out.append(("table", [fr[0]] + earlier))
        out.append(("cap", "Table 32.73.G. Formulas defined before v8 but not printed in Sections 32.62-32.72 "
                           "(completes the Methodology's set: with Tables 32.62, 32.70, 32.71.F, 32.72.F/G and "
                           "32.73.F every formula is printed)."))
    out.append(("p", END_MARK))
    return out


def _status_text():
    c = json.loads((ROOT / "phase17" / "data" / "defence_v8" / "closure_v8.json").read_text(encoding="utf-8"))
    g = list(c["gaps"].items())
    now = "; ".join(f"{k.split(': ')[-1]} {v.get('after_v8', v.get('after_v7')) * 100:.0f}%" for k, v in g)
    return (f"After Defence v8 (Section 32.73) the evidence-based operational closure under the frozen rubric is: "
            f"{now}. Gap 1 is unchanged from v7. Gap 2 rises through a properly powered factual-payload containment "
            "test on fresh roots, which clears the generation-4 withholding bar v7's own test fell short of. Gap 3 "
            "rises through a writer-authenticated detection gate, confirmed on a fresh, owner-disjoint corpus, that "
            "clears both the detection and legitimate-rule limits at one operating point for the first time in this "
            "programme's held-out record; the gate's own operating boundary -- a compromised trusted-writer key -- "
            "is measured and reported alongside the result.")


def _set_par_text(p, t):
    for r in p.runs[1:]:
        r._r.getparent().remove(r._r)
    if p.runs:
        p.runs[0].text = t
    else:
        p.add_run(t)


def run() -> dict:
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.shared import Inches
    from docx.text.paragraph import Paragraph

    from phase17.figures_v8 import run as draw

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
        v7_end = next((p for p in doc.paragraphs if p.text == "[End of the Defence v7 update.]"), None)
        ins_el = v7_end._p.getnext() if v7_end is not None else anchor._p
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

    txt = _status_text()
    ex8 = next((p for p in doc.paragraphs if p.text.startswith((STATUS8, "After Defence v8"))), None)
    ex7 = next((p for p in doc.paragraphs if p.text.startswith(STATUS7_CURRENT)), None)
    if ex7 is not None and not ex7.text.endswith(V7_POINTER):
        ex7.add_run(V7_POINTER)
    if ex8 is not None:
        for r in ex8.runs[1:]:
            r._r.getparent().remove(r._r)
        ex8.runs[0].text = txt
    elif ex7 is not None:
        el = OxmlElement("w:p")
        ex7._p.addnext(el)
        Paragraph(el, ex7._parent).add_run(txt)
    else:
        anchor.insert_paragraph_before(txt)
    log["status"] = txt[:200]

    from phase17.editorial_pass import apply_to
    log["editorial"] = apply_to(doc, "methodology")      # professional-prose edits, numbers verified; run last

    # Extend the reading guide's section range to include v8 (idempotent).
    guide_old = "The pre-registered defence programmes v2-v7 and the closure of the three research gaps are Sections 32.64-32.72,"
    guide_new = ("The pre-registered defence programmes v2-v8 and the closure of the three research gaps are Sections "
                "32.64-32.73,")
    g = next((p for p in doc.paragraphs if guide_old in p.text), None)
    if g is not None:
        _set_par_text(g, g.text.replace(guide_old, guide_new))
        log["reading_guide"] = "applied"
    else:
        log["reading_guide"] = "already" if any(guide_new in p.text for p in doc.paragraphs) else "missing"

    # Extend the closure-history line the editorial currency pass recorded through v7 (idempotent).
    cl8 = json.loads((ROOT / "phase17" / "data" / "defence_v8" / "closure_v8.json").read_text(encoding="utf-8"))
    hist = next((p for p in doc.paragraphs if p.text.startswith("Operational closure (Sections 32.70-32.72, 33).")), None)
    v8_clause = (" After Defence v8 (Section 32.73): " +
                 ", ".join(f"{g.split(': ')[1]} {100 * v.get('after_v8', v.get('after_v7')):.1f}%"
                           for g, v in cl8["gaps"].items()) + ".")
    if hist is not None and "After Defence v8" not in hist.text:
        hist.add_run(v8_clause)
        log["closure_history_extended"] = True

    doc.save(str(DOC))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, indent=1), encoding="utf-8")
    return log


if __name__ == "__main__":
    print(run())
