"""Phase 3.3-V5 -- generates CANDIDATE multi-reference gold aliases for all 120
real LoCoMo tasks in the frozen formal sample, per the "multi-reference gold
answers" suggestion (SQuAD-style: 2-4 acceptable phrasings per question).

CRITICAL, DISCLOSED LIMITATION -- THESE ARE UNVERIFIED CANDIDATES, NOT GOLD
--------------------------------------------------------------------------------
Every alias here is LLM-generated, NOT human-verified. The n=15 hand-reviewed
pilot (this session) found zero factual errors in ~41 candidates, but that is a
small sample reviewed by one person -- it does NOT license treating this file's
output as trustworthy gold without a real human review pass. This file is
explicitly a CANDIDATE list for that review, never wired into any scoring script
as if it were verified. The original gold answer field in the benchmark is never
touched, read, or modified by anything downstream of this -- this produces a
SEPARATE, clearly-labeled file.

ROBUSTNESS -- MALFORMED JSON DOES HAPPEN (confirmed in the n=15 pilot: one output
had missing commas between array elements) -- this script retries once on a parse
failure and records the failure explicitly if both attempts fail, rather than
silently dropping the task or crashing the whole run.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from phase3.evaluation.llm.provider import LlamaServerEndpoint, LlamaServerProvider, clean_baseline_generation_config

SYSTEM_PROMPT = (
    "You generate alternative phrasings of a gold answer to a question, for QA "
    "evaluation purposes. Given a question and its gold answer, output 2-3 short, "
    "natural alternative phrasings that mean EXACTLY the same thing -- do not add "
    "new information, do not remove key details, do not change the meaning. Output "
    "ONLY a JSON array of strings, nothing else."
)

_DATASET = _REPO_ROOT / "phase3" / "experiments" / "results" / "canonical_store" / "v3_hybrid_candidate" / "dataset_full" / "clean_agent_dataset_v3_hybrid_locomo_120x2.json"
_DATA_ROOT = _REPO_ROOT / "data" / "processed"
_OUT_DIR = Path(__file__).resolve().parent / "results"


def _extract_json_array(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            return parsed, None
        return None, "parsed but not a list of strings"
    except json.JSONDecodeError as exc:
        # Try a common repair: missing commas between adjacent quoted strings, e.g. '"a" "b"' -> '"a", "b"'
        repaired = re.sub(r'"\s+"', '", "', text)
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                return parsed, "repaired missing-comma JSON"
        except json.JSONDecodeError:
            pass
        return None, f"JSONDecodeError: {exc}"


def main():
    def log(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

    with _DATASET.open(encoding="utf-8") as f:
        hybrid = json.load(f)
    task_ids = sorted(set(r["task_id"] for r in hybrid))

    task_records = {}
    with open(_DATA_ROOT / "locomo" / "task_records.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            task_records[r["task_id"]] = r

    endpoint = LlamaServerEndpoint()
    llm_provider = LlamaServerProvider(endpoint)
    identity = llm_provider.verify_server_identity()
    log(f"Server identity verified: {identity}")
    gen_config = clean_baseline_generation_config(n_ctx=4096, max_tokens=150)

    results = {}
    n_clean, n_repaired, n_failed = 0, 0, 0
    for i, tid in enumerate(task_ids):
        t = task_records.get(tid)
        if t is None:
            continue
        q, gold = t["question"], str(t["answer"])
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {q}\nGold answer: {gold}"},
        ]

        parsed, repair_note, raw_text = None, None, None
        for attempt in range(2):
            gen_result = llm_provider.generate(messages, gen_config)
            raw_text = gen_result.text
            parsed, err = _extract_json_array(raw_text)
            if parsed is not None:
                repair_note = err  # None or "repaired missing-comma JSON"
                break

        if parsed is not None:
            if repair_note:
                n_repaired += 1
            else:
                n_clean += 1
        else:
            n_failed += 1
            parsed = []

        results[tid] = {
            "question": q, "gold": gold, "candidate_aliases": parsed,
            "raw_llm_output": raw_text, "repair_note": repair_note,
            "verified_by_human": False,  # explicit, disclosed -- never silently implied otherwise
        }

        if (i + 1) % 20 == 0:
            log(f"  generated {i+1}/{len(task_ids)}")

    out_path = _OUT_DIR / "multiref_gold_aliases_UNVERIFIED.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"Wrote {out_path}")
    log(f"n_clean_json={n_clean} n_repaired_json={n_repaired} n_failed_json={n_failed} (out of {len(task_ids)})")
    log("REMINDER: every entry has verified_by_human=False. Do not wire this into any scoring script as if it were verified gold.")


if __name__ == "__main__":
    main()
