"""Editorial pass for the two deliverable documents (2026-10-18): professional prose without filler, numbers unchanged.

Edits are stored per document in phase17/editorial/<doc>_edits.json as {sha256(original paragraph text): {"new": text}}.
`apply` replaces a paragraph only if its current text hashes to a stored key AND the new text contains exactly the same
multiset of numeric tokens as the original (every count, rate, p-value, date and section number survives); otherwise the
paragraph is left as it is and the mismatch is logged. Applying is idempotent (an edited paragraph no longer matches its
key). Formatting: a bold first run that prefixes both texts (e.g. 'Method:') is kept bold; the rest takes the first
non-bold run's formatting.

  python -m phase17.editorial_pass export <methodology|results> <out.json> [--all] [--from N] [--to M]
  python -m phase17.editorial_pass check <methodology|results> <edits_chunk.json>     (verify, then merge into the store)
  python -m phase17.editorial_pass apply <methodology|results>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "phase17" / "editorial"
DOCS = {"methodology": ROOT / "Methodology Draft.docx", "results": ROOT / "MAMBench Results Analysis.docx"}
NUM = re.compile(r"(?<![A-Za-z_\d])\d[\d,]*(?:\.\d+)?(?:e-?\d+)?%?")
FILLER = re.compile(r"\b(real|really|genuine(ly)?|actual(ly)?|honest(ly)?|truly|simply|silently|smoothed|merely|"
                    r"deliberately|indeed|candid(ly)?|in full|turns out)\b", re.I)
CAPS = re.compile(r"(NOT|ONCE|ONLY|STRICTLY|SAME|NEW|HARDER|EASIER|EVERY|ALL|BEFORE|AFTER|TESTED|EVALUATED|MONITORING|"
                  r"ACTIVATION|MEMORY-POISONING|NEVER|ALWAYS|BOTH|EITHER|ANY|WITHOUT|MUST|ACTUALLY|REAL|EXACTLY|LIVE|"
                  r"WORKING|FULL|DIRECT|HOLDS|FAILED|HELD|ARE|IS|WAS|DOES|DID)")
INFORMAL = re.compile(r"(\?\s*$|we.{0,15}found|paid off|the honest|simply|very|quite|"
                      r"disclosed rather|rather than (silently|assumed|asserted)|not merely)", re.I)
PROTECTED_STARTS = ("Appendix A — Exact Prompts", "16. References")   # verbatim sections: never edited
PROTECTED_END_HEADINGS = ("Appendix", "17. Phase 4")


def sha(t: str) -> str:
    """Hash of the paragraph text with dash typography undone, so edits keep matching after normalisation."""
    return hashlib.sha256(t.replace(" – ", " -- ").encode("utf-8")).hexdigest()


def nums(t: str) -> Counter:
    return Counter(x.rstrip(".,").replace(",", "") for x in NUM.findall(t))


def _store(doc: str) -> dict:
    p = STORE / f"{doc}_edits.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _protected_indices(d) -> set:
    """Paragraph indices inside verbatim sections (exact prompts; reference lists)."""
    out, inside = set(), False
    for i, p in enumerate(d.paragraphs):
        t = p.text.strip()
        if p.style.name.startswith("Heading 1"):
            inside = t.startswith(PROTECTED_STARTS)
        if inside:
            out.add(i)
    return out


def export(doc: str, out: str, all_paras=False, lo=0, hi=10 ** 9):
    import docx

    d = docx.Document(str(DOCS[doc]))
    prot = _protected_indices(d)
    store = _store(doc)
    rows = []
    for i, p in enumerate(d.paragraphs):
        t = p.text
        if not t.strip() or i in prot or not (lo <= i < hi) or p.style.name.startswith("Title"):
            continue
        if sha(t) in store:
            continue
        if not all_paras and not (FILLER.search(t) or CAPS.search(t) or INFORMAL.search(t)):
            continue
        rows.append({"i": i, "style": p.style.name, "sha": sha(t), "text": t})
    Path(out).write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"exported {len(rows)} paragraphs, {sum(len(r['text'].split()) for r in rows)} words")


def check(doc: str, chunk: str) -> dict:
    """chunk: [{'sha', 'new'}] (other keys ignored). Verifies numbers against the current document text, then merges."""
    import docx

    d = docx.Document(str(DOCS[doc]))
    cur = {sha(p.text): p.text for p in d.paragraphs}
    store = _store(doc)
    bad, ok = [], 0
    for e in json.loads(Path(chunk).read_text(encoding="utf-8")):
        full = [k for k in cur if k.startswith(e["sha"])]          # a unique prefix of the paragraph hash is enough
        if len(full) == 1:
            e["sha"] = full[0]
        orig = cur.get(e["sha"])
        if orig is None:
            bad.append((e["sha"][:10], "paragraph not found"))
            continue
        if nums(orig) != nums(e["new"]):
            bad.append((e["sha"][:10], f"numbers differ: missing {dict(nums(orig) - nums(e['new']))}, "
                                       f"added {dict(nums(e['new']) - nums(orig))}"))
            continue
        store[e["sha"]] = {"new": e["new"], "orig_head": orig[:60]}
        ok += 1
    STORE.mkdir(parents=True, exist_ok=True)
    (STORE / f"{doc}_edits.json").write_text(json.dumps(store, indent=0, ensure_ascii=False), encoding="utf-8")
    print(f"merged {ok}; rejected {len(bad)}")
    for b in bad:
        print("  REJECTED", b)
    return {"merged": ok, "rejected": bad}


def _replace(p, new: str):
    runs = p.runs
    if not runs:
        p.add_run(new)
        return
    keep_bold = runs[0].bold and len(runs) > 1 and p.text.startswith(runs[0].text) and new.startswith(runs[0].text) \
        and runs[0].text.strip()
    if keep_bold:
        body = next((r for r in runs[1:] if not r.bold), runs[1])
        body.text = new[len(runs[0].text):]
        for r in runs[1:]:
            if r is not body:
                r._r.getparent().remove(r._r)
    else:
        base = next((r for r in runs if not r.bold), runs[0])
        base.text = new
        for r in runs:
            if r is not base:
                r._r.getparent().remove(r._r)


def _typography(d) -> int:
    """' -- ' used as a dash becomes a spaced en dash, run by run (formatting kept); verbatim sections untouched."""
    prot, n = _protected_indices(d), 0
    for i, p in enumerate(d.paragraphs):
        if i in prot:
            continue
        for r in p.runs:
            if " -- " in r.text:
                r.text = r.text.replace(" -- ", " – ")
                n += 1
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        if " -- " in r.text:
                            r.text = r.text.replace(" -- ", " – ")
                            n += 1
                        for old, new in CELL_FIXES:
                            if old in r.text:
                                r.text = r.text.replace(old, new)
    return n


# Table cells are short labels outside the paragraph store; these phrase-level fixes keep every number
CELL_FIXES = (
    ("verified against a genuinely non-trivial competing pool", "verified against a non-trivial competing pool"),
    ("a genuinely different kind of finding", "a different kind of finding"),
    ("Real, genuinely gradient-optimized artifact", "Gradient-optimized artifact"),
    ("(genuinely disjoint scenarios)", "(disjoint scenarios)"),
)


def apply_to(d, doc: str) -> dict:
    store = _store(doc)
    log = {"applied": 0, "number_mismatch": 0}
    for p in d.paragraphs:
        e = store.get(sha(p.text))
        if not e:
            continue
        if nums(p.text) != nums(e["new"]):
            log["number_mismatch"] += 1
            continue
        _replace(p, e["new"])
        log["applied"] += 1
    log["dashes_normalised"] = _typography(d)
    return log


def apply(doc: str) -> dict:
    import docx

    d = docx.Document(str(DOCS[doc]))
    log = apply_to(d, doc)
    d.save(str(DOCS[doc]))
    (STORE / f"{doc}_apply_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    return log


if __name__ == "__main__":
    a = sys.argv
    if a[1] == "export":
        lo = int(a[a.index("--from") + 1]) if "--from" in a else 0
        hi = int(a[a.index("--to") + 1]) if "--to" in a else 10 ** 9
        export(a[2], a[3], "--all" in a, lo, hi)
    elif a[1] == "check":
        check(a[2], a[3])
    else:
        print(apply(a[2]))
