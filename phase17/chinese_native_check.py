"""Phase 17 fix (external review round 4, 2026-09-29) -- does B12's Chinese result survive
once the translation confound is removed?

The reviewer's point: the 84 `held_out_zh` attacks are Qwen's translations of English
attacks, B12's live route translates CJK text back to English with the SAME Qwen model
(so it can largely undo its own translation), and the Chinese benign control (PerLTQA) is
native text while the attacks are machine-translated. This script re-runs the comparison on
the two populations `chinese_native_attacks.py` built to close that gap:

  * 30 attacks composed DIRECTLY in Chinese by Gemini (a different model family; never
    shown an English attack to translate), and
  * a machine-translated benign control (real English LoCoMo text translated to Chinese by
    Qwen through the same pipeline the translated attacks went through),

alongside the original 84 translated attacks and the native PerLTQA benign half, for all
three routes (translate-then-score = shipped, multilingual embedding, union). It also
runs the full live B12 decision (`apply_defense("B12", ...)` on the standard
`isolated_arena` pools) on the native attacks and the translated benign control, so the
headline is the shipped config's own number, not only the detector's.

Nothing here tunes anything: the detectors are loaded/fit exactly as `chinese_ensemble.py`
does (dev pool only), and the populations are fixed caches.
"""
from __future__ import annotations

import json
from pathlib import Path

from phase17.chinese_native_attacks import native_zh_records, translated_benign_texts
from phase17.multilingual_stacked import MultilingualDetector
from phase17.perltqa import perltqa_pools
from phase17.stacked_detector import StackedDetector
from phase17.stats import rate_with_ci
from phase17.translation import zh_records
from phase17.tune_lomo import dev_pool

OUT = Path(__file__).parent / "data" / "chinese_native_results.json"


def _routes(det_en, det_ml, texts):
    tr = det_en.decide(texts, 0.005, route="translate")
    ml = det_ml.decide(texts, 0.005)
    un = [a or b for a, b in zip(tr, ml)]
    n = len(texts)
    return {"n": n, "translate": rate_with_ci(sum(tr), n), "multilingual": rate_with_ci(sum(ml), n),
            "union": rate_with_ci(sum(un), n)}


def _live_b12(records):
    from phase14.defended_retrieval import CONFIG_B12_STACKED, apply_defense
    from phase17 import arenas

    pools, truth = arenas.isolated_arena(records)
    ids = {r.scenario_id for r in records}
    excl = flag = 0
    by_mech = {}
    for p in pools:
        items = tuple((m.scenario_id, m.content_text) for m in p.memories)
        _, decisions = apply_defense(CONFIG_B12_STACKED, items)
        for d in decisions:
            if d.memory_id in ids:
                excl += d.excluded
                flag += d.action != "ALLOW"
                fam = truth[d.memory_id].family
                b = by_mech.setdefault(fam, [0, 0])
                b[0] += d.excluded
                b[1] += 1
    n = len(records)
    return {"n": n, "excluded": rate_with_ci(excl, n), "flagged": rate_with_ci(flag, n),
            "excluded_by_mechanism": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_mech.items())}}


def _live_b12_benign(texts):
    """Benign texts, each scored in its own 4-item pool with 3 other benign items from the
    same population (no poison present), mirroring how the benign PerLTQA half is pooled."""
    from phase14.defended_retrieval import CONFIG_B12_STACKED, apply_defense

    excl = flag = 0
    for i in range(0, len(texts), 4):
        items = tuple((f"ZHB-{i + j}", t) for j, t in enumerate(texts[i:i + 4]))
        _, decisions = apply_defense(CONFIG_B12_STACKED, items)
        excl += sum(d.excluded for d in decisions)
        flag += sum(d.action != "ALLOW" for d in decisions)
    n = len(texts)
    return {"n": n, "excluded": rate_with_ci(excl, n), "flagged": rate_with_ci(flag, n)}


def main() -> dict:
    translated_attacks = [r.text for r in zh_records()]
    native = native_zh_records()
    native_attacks = [r.text for r in native]
    mt_benign = translated_benign_texts()
    te = sorted(perltqa_pools()[0], key=lambda p: p.pool_id)[1::2]
    native_benign = [m.content_text for p in te for m in p.memories]

    det_en = StackedDetector.load(Path(__file__).parent / "data" / "stacked_model.json")
    pos, neg = dev_pool()
    det_ml = MultilingualDetector()
    det_ml.fit([x["text"] for x in pos + neg], [x["label"] for x in pos + neg], [x["group"] for x in pos + neg])

    out = {
        "detector_routes": {
            "attacks_translated_by_qwen (original 84)": _routes(det_en, det_ml, translated_attacks),
            "attacks_native_chinese_by_gemini": _routes(det_en, det_ml, native_attacks),
            "benign_native_perltqa (test half)": _routes(det_en, det_ml, native_benign),
            "benign_machine_translated_by_qwen": _routes(det_en, det_ml, mt_benign),
        },
        "live_b12": {
            "attacks_native_chinese_by_gemini": _live_b12(native),
            "benign_machine_translated_by_qwen": _live_b12_benign(mt_benign),
        },
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = main()
    for k, v in r["detector_routes"].items():
        print(f"{k:45s} n={v['n']:4d} translate={v['translate']['k']:3d} multilingual={v['multilingual']['k']:3d} "
              f"union={v['union']['k']:3d}")
    for k, v in r["live_b12"].items():
        print("live B12", k, "excluded", v["excluded"]["k"], "/", v["n"], "flagged", v["flagged"]["k"], "/", v["n"],
              v.get("excluded_by_mechanism", ""))
    print("DONE")
