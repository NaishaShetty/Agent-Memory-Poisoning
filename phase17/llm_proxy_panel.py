"""Phase 17 fix round 5 -- a SECOND, independent LLM-proxy rater (phi3:mini, local, no
rate limit) on the SAME blinded 60-item packet, so the human-evaluation gap has a real
2-model panel (Gemini + phi3) instead of one rate-limited hosted model. Inter-proxy
agreement is itself a real, useful data point: if two independently-different model
families agree with each other and with the automated judge, that is stronger evidence
than either alone -- but it is STILL not a human rating, and is labeled as such
everywhere."""

from __future__ import annotations

import json
from pathlib import Path

from phase17.llm_proxy_human_eval import CATEGORIES, PROMPT

DATA = Path(__file__).parent / "data"


def run() -> dict:
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase3.evaluation.llm.provider import GenerationConfig

    packet = json.loads((DATA / "human_eval_packet_blind.json").read_text(encoding="utf-8"))
    key = json.loads((DATA / "human_eval_packet_key.json").read_text(encoding="utf-8"))
    gemini_res = json.loads((DATA / "llm_proxy_human_eval_results.json").read_text(encoding="utf-8"))
    gemini_by_id = {r["item_id"]: r["gemini_label"] for r in gemini_res["ratings"]}

    phi3 = OllamaProvider(model="phi3:mini")
    cfg = GenerationConfig(temperature=0.0, seed=17, max_tokens=8, enable_thinking=False, n_ctx=2048, request_timeout_sec=60.0)

    ratings = []
    for item in packet:
        prompt = PROMPT.format(question=item["question"], gold=item["gold_answer"], answer=item["model_answer"] or "(no answer)")
        try:
            r = phi3.generate([{"role": "user", "content": prompt}], cfg)
            label = r.text.strip().lower()
            label = next((c for c in CATEGORIES if c in label), "ambiguous")
        except Exception as exc:
            label = f"ERROR:{type(exc).__name__}"
        ratings.append({"item_id": item["item_id"], "phi3_label": label})

    def is_correct(label: str) -> bool:
        return label in ("correct", "paraphrase")

    n_both = agree_gp = agree_pj = agree_gj = 0
    for r in ratings:
        gid, phi3_label = r["item_id"], r["phi3_label"]
        glabel = gemini_by_id.get(gid)
        k = key.get(str(gid)) or key.get(gid)
        if phi3_label.startswith("ERROR") or glabel is None or glabel.startswith("ERROR") or k is None:
            continue
        n_both += 1
        agree_gp += (is_correct(glabel) == is_correct(phi3_label))
        agree_pj += (is_correct(phi3_label) == bool(k["llm_judge"]))
        agree_gj += (is_correct(glabel) == bool(k["llm_judge"]))
        panel_majority = sum([is_correct(glabel), is_correct(phi3_label), bool(k["llm_judge"])]) >= 2

    out = {
        "n_items": len(ratings), "n_both_defined": n_both,
        "gemini_vs_phi3_agreement": agree_gp / n_both if n_both else None,
        "phi3_vs_qwen_judge_agreement": agree_pj / n_both if n_both else None,
        "gemini_vs_qwen_judge_agreement": agree_gj / n_both if n_both else None,
        "label_distribution_phi3": {c: sum(1 for r in ratings if r["phi3_label"] == c) for c in CATEGORIES},
        "ratings": ratings,
        "disclosure": "TWO LLM PROXIES (Gemini + phi3:mini), NOT human raters. A 2-model panel is stronger "
                     "evidence than either alone but does not substitute for a real human evaluation of this "
                     "SAME packet (still open; see HUMAN_EVAL_INSTRUCTIONS.md).",
    }
    (DATA / "llm_proxy_panel_results.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: v for k, v in r.items() if k != "ratings"}, indent=1))
    print("DONE")
