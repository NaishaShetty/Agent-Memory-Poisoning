"""Structural tests for the live-foundation stage scripts (`phase17/amem_live/`,
`phase17/mem0_live/`), which external review correctly noted had NO tests at all --
which is how a per-case-vs-global-lookup bug went unnoticed in `mem0_live/stage2_defend.py`.
These do not require a running A-mem-sys/Mem0 install.
"""
import json


def _fake_stage1_data():
    """Three synthetic cases shaped exactly like `stage1_out.json`: the SAME poison_id
    reused across original/plain/embedded variants, with DELIBERATELY DIFFERENT text per
    variant -- this is exactly the shape that exposed the real Mem0 bug."""
    return [
        {"kind": "poison_original", "id": "c-orig", "poison_id": "P0",
         "items": [["P0", "ORIGINAL TEXT"], ["D1", "distractor one"]], "retrieved_ids": ["P0", "D1"]},
        {"kind": "poison_plain", "id": "c-plain", "poison_id": "P0",
         "items": [["P0", "PLAIN REWRITE TEXT"], ["D1", "distractor one"]], "retrieved_ids": ["P0", "D1"]},
        {"kind": "poison_embedded", "id": "c-embed", "poison_id": "P0",
         "items": [["P0", "EMBEDDED REWRITE TEXT"], ["D1", "distractor one"]], "retrieved_ids": ["P0", "D1"]},
    ]


def test_mem0_stage2_per_case_lookup_regression_guard():
    """The regression test for the exact bug external review found -- and, per review
    round 2, calls the REAL production function (`resolve_case_items`), not a re-
    implementation of it, so a future regression to the buggy global-dict pattern inside
    `stage2_defend.py` itself is actually caught here rather than only in a copy of the
    logic that lives solely in this test file."""
    from phase17.mem0_live.stage2_defend import resolve_case_items

    data = _fake_stage1_data()
    resolved = {c["kind"]: dict(resolve_case_items(c))["P0"] for c in data}

    assert resolved["poison_original"] == "ORIGINAL TEXT"
    assert resolved["poison_plain"] == "PLAIN REWRITE TEXT"
    assert resolved["poison_embedded"] == "EMBEDDED REWRITE TEXT"

    # demonstrate the BUG this guards against: the old global-dict pattern collapses all
    # three onto whichever text was written last
    buggy_global = {mid: t for c in data for mid, t in c["items"]}
    assert buggy_global["P0"] == "EMBEDDED REWRITE TEXT"  # NOT the original -- this was the real bug
    assert buggy_global["P0"] != resolved["poison_original"]


def test_amem_stage2_uses_per_case_retrieved_content():
    """Structural check that the A-MEM stage-2 script's own per-case pattern (which
    external review confirmed was correct) has not regressed to the buggy global-lookup
    shape the Mem0 script had."""
    src = open("phase17/amem_live/stage2_defend.py", encoding="utf-8").read()
    assert 'r["content"]' in src  # reads each case's OWN retrieved content, per case
    assert "text_by_id = {mid: t for c in data for mid, t in c" not in src
