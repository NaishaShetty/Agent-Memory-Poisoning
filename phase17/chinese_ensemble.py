"""Phase 17 fix round 4 -- Chinese detection ensemble: does UNIONING the translation-route
stacked detector (English embeddings + translated text) with the multilingual-embedding
detector (no translation) catch more than either alone? Different mechanisms (lexical
match on a translation vs. genuine cross-lingual embedding alignment) may miss different
cases, so a union could exceed both -- tested directly, not assumed."""
import json
from pathlib import Path

from phase17.multilingual_stacked import MultilingualDetector
from phase17.perltqa import perltqa_pools
from phase17.stacked_detector import StackedDetector
from phase17.stats import rate_with_ci
from phase17.translation import zh_records
from phase17.tune_lomo import dev_pool

OUT = Path(__file__).parent / "data" / "chinese_ensemble_results.json"


def main():
    zh = zh_records()
    tx = [r.text for r in zh]

    det_en = StackedDetector.load(Path(__file__).parent / "data" / "stacked_model.json")
    excl_translate = det_en.decide(tx, 0.005, route="translate")

    pos, neg = dev_pool()
    det_ml = MultilingualDetector()
    det_ml.fit([x["text"] for x in pos + neg], [x["label"] for x in pos + neg], [x["group"] for x in pos + neg])
    excl_ml = det_ml.decide(tx, 0.005)

    union = [a or b for a, b in zip(excl_translate, excl_ml)]
    only_translate = sum(a and not b for a, b in zip(excl_translate, excl_ml))
    only_ml = sum(b and not a for a, b in zip(excl_translate, excl_ml))
    both = sum(a and b for a, b in zip(excl_translate, excl_ml))

    te = sorted(perltqa_pools()[0], key=lambda p: p.pool_id)[1::2]
    bt = [m.content_text for p in te for m in p.memories]
    excl_translate_b = det_en.decide(bt, 0.005, route="translate")
    excl_ml_b = det_ml.decide(bt, 0.005)
    union_b = [a or b for a, b in zip(excl_translate_b, excl_ml_b)]

    out = {
        "n_zh": len(zh), "excluded_translate_only": rate_with_ci(sum(excl_translate), len(zh)),
        "excluded_multilingual_only": rate_with_ci(sum(excl_ml), len(zh)), "excluded_union": rate_with_ci(sum(union), len(zh)),
        "only_translate_caught": only_translate, "only_multilingual_caught": only_ml, "both_caught": both,
        "benign_n": len(bt), "benign_excluded_translate": rate_with_ci(sum(excl_translate_b), len(bt)),
        "benign_excluded_multilingual": rate_with_ci(sum(excl_ml_b), len(bt)), "benign_excluded_union": rate_with_ci(sum(union_b), len(bt)),
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=1))
    print("DONE")


if __name__ == "__main__":
    main()
