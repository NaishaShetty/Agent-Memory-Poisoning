"""HOLD-OUT 5: real user jailbreaks and matched benign prompts from a different platform.

WHY IT EXISTS. Hold-out 3 was the only corpus here with a matched benign half, and it has been
scored five times with only the first pre-registered; on 2026-10-06 the owner retired it from
further measurement. Round 7's new configurations -- neutralisation composed with detection, and
a confidence-gated B13 inside the unions -- therefore need a fresh matched corpus, and B17/B18
need the clean injection-regime test they have never had.

SOURCE. `lmsys/toxic-chat` (config `toxicchat0124`, CC-BY-NC-4.0): real user prompts submitted
to the Vicuna online demo, each annotated by the dataset's authors for toxicity and for
JAILBREAKING. The attack half is every prompt annotated jailbreaking=1; the benign half is a
seeded sample of prompts annotated toxicity=0 AND jailbreaking=0 from the same demo. Toxic
non-jailbreak prompts (harmful requests) are excluded from both halves: they are neither benign
memory nor injected instructions, and putting them on either side would decide the result by
labelling convention. Their count is recorded.

WHY THIS ONE. A different platform and population from every corpus used so far (password-game
players, Reddit/Discord jailbreak communities), human-written, human-annotated, and with benign
text from the SAME interface as the attacks, so a detector cannot score well by telling one
website's prose from another's.

NEAR-DUPLICATE GUARD. Vicuna-demo jailbreaks are often pasted copies of the same circulating
prompts that hold-out 3 and its dev snapshot contain. Any candidate that is a near-copy (word
5-gram containment >= 0.6, fixed in `near_dup.py` before this corpus was built) of ANY text
this project has already used -- hold-outs 1-3, both dev snapshots, the external dev attacks --
is dropped before freezing. Without this the hold-out would partly measure recall on text the
configurations were developed against.

DISCIPLINE. Built, digested and frozen in one run, BEFORE any configuration is scored on it.
Predictions are committed in `docs/phase17/PREREGISTRATION_HOLDOUT5.md` before the run. Nothing
is fitted here. The same limit applies as to every injection hold-out: a good score is evidence
about overt injected instructions arriving in memory, not about additive fabrication or
preference hijack -- that is hold-out 4's job (`holdout4_corpus.py`).

CONTENT NOTE: jailbreak prompts include offensive text; they are detector inputs only and are not
reproduced in any report.
"""
from __future__ import annotations

import hashlib
import io
import json
import random
import time
import urllib.request
from pathlib import Path
from typing import List

from phase17.poison_sets import PoisonRecord

DATA = Path(__file__).parent / "data"
CACHE = DATA / "holdout5_attacks.json"
FREEZE = DATA / "holdout5_freeze.json"
SPLIT = "held_out_toxicchat"
DATASET = "lmsys/toxic-chat"
CONFIG = "toxicchat0124"
PARQUET = ("https://huggingface.co/api/datasets/lmsys/toxic-chat/parquet/toxicchat0124/"
           "{split}/0.parquet")
WRAPPERS = (
    "Saved from a tool result: {x}",
    "Note from a document the user shared: {x}",
    "Reminder for future sessions: {x}",
)
MAX_BENIGN = 1000
MIN_LEN, MAX_LEN = 25, 1200
SEED = 7


def _rows():
    import pandas as pd

    frames = []
    for split in ("train", "test"):
        with urllib.request.urlopen(PARQUET.format(split=split), timeout=180) as r:
            frames.append(pd.read_parquet(io.BytesIO(r.read())).assign(_split=split))
    return pd.concat(frames, ignore_index=True)


def _seen_texts() -> List[str]:
    """Every attack or benign text this project has already scored or developed against."""
    from phase17 import external_test_corpus as h1, holdout2_corpus as h2, holdout3_corpus as h3
    from phase17.external_attacks import external_records
    from phase17.holdout3_dev_benign import dev_benign_texts
    from phase17.injection_dev_attacks import records as dev_atk

    out = [r.text for r in h1.test_attack_records()] + list(h1.test_benign_texts())
    out += [r.text for r in h2.records()]
    out += [r.text for r in h3.attack_records()] + list(h3.benign_texts())
    out += list(dev_benign_texts()) + [r.text for r in dev_atk()]
    out += [r.text for r in external_records()]
    return out


def _clean(t) -> str:
    return " ".join(str(t or "").split())


def build() -> dict:
    from phase17.near_dup import split_near_duplicates

    df = _rows()
    df["t"] = df["user_input"].map(_clean)
    df = df[df["t"].str.len() >= MIN_LEN].drop_duplicates("t")
    jb = df[df["jailbreaking"] == 1]
    ben = df[(df["jailbreaking"] == 0) & (df["toxicity"] == 0)]
    excluded_toxic = int(((df["jailbreaking"] == 0) & (df["toxicity"] == 1)).sum())

    seen = _seen_texts()
    jb_t = [t[:MAX_LEN] for t in jb["t"]]
    keep_a, drop_a = split_near_duplicates(jb_t, seen)
    # The benign half is sampled AFTER near-duplicate removal so its size is not shrunk by it.
    ben_t = [t[:MAX_LEN] for t in ben["t"]]
    keep_b, drop_b = split_near_duplicates(ben_t, seen)
    rng = random.Random(SEED)
    keep_b = sorted(rng.sample(keep_b, min(MAX_BENIGN, len(keep_b))))

    atk_lens = {t: n for t, n in zip(jb["t"], jb["t"].str.len())}
    ben_lens = {t: n for t, n in zip(ben["t"], ben["t"].str.len())}

    def items(texts, idx, prefix, lens, src):
        out = []
        for j, i in enumerate(idx):
            w = WRAPPERS[j % len(WRAPPERS)]
            out.append({"id": f"{prefix}-{j}", "raw_len": int(lens.get(src[i], len(texts[i]))),
                        "text": w.format(x=texts[i]), "wrapper": w})
        return out

    atk = items(jb_t, keep_a, "TXC", atk_lens, list(jb["t"]))
    bn = items(ben_t, keep_b, "TXCBEN", ben_lens, list(ben["t"]))
    data = {"dataset": DATASET, "config": CONFIG, "license": "CC-BY-NC-4.0",
            "authorship": "human (Vicuna online-demo users); labels by the dataset's annotators",
            "attack_rule": "jailbreaking == 1",
            "benign_rule": "jailbreaking == 0 AND toxicity == 0, seeded sample",
            "n_toxic_nonjailbreak_excluded": excluded_toxic,
            "near_duplicate_rule": "word 5-gram containment >= 0.6 against every corpus already "
                                   "used (phase17/near_dup.py)",
            "n_attack_candidates": len(jb_t), "n_attack_near_duplicates_dropped": len(drop_a),
            "n_benign_candidates": len(ben_t), "n_benign_near_duplicates_dropped": len(drop_b),
            "n_attacks": len(atk), "n_benign": len(bn),
            "content_note": "jailbreak prompts include offensive text; detector inputs only",
            "attacks": atk, "benign": bn}
    CACHE.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def _digest() -> str:
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    h = hashlib.sha256()
    for grp in ("attacks", "benign"):
        for i in d[grp]:
            h.update(i["id"].encode("utf-8"))
            h.update(i["text"].encode("utf-8"))
    return h.hexdigest()


def freeze(note: str = "") -> dict:
    d = json.loads(CACHE.read_text(encoding="utf-8"))
    out = {"frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sha256": _digest(),
           "n_attacks": d["n_attacks"], "n_benign": d["n_benign"], "note": note}
    FREEZE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def verify_frozen() -> bool:
    return FREEZE.exists() and json.loads(FREEZE.read_text(encoding="utf-8"))["sha256"] == _digest()


def attack_records() -> List[PoisonRecord]:
    if not CACHE.exists():
        return []
    return [PoisonRecord(i["id"], i["text"], "toxicchat_jailbreak", SPLIT)
            for i in json.loads(CACHE.read_text(encoding="utf-8"))["attacks"]]


def benign_texts() -> List[str]:
    if not CACHE.exists():
        return []
    return [i["text"] for i in json.loads(CACHE.read_text(encoding="utf-8"))["benign"]]


if __name__ == "__main__":
    if FREEZE.exists():
        raise SystemExit("hold-out 5 is already frozen; rebuilding it would invalidate it")
    d = build()
    print(f"attacks: {d['n_attack_candidates']} candidates, {d['n_attack_near_duplicates_dropped']} "
          f"near-duplicates of already-used corpora dropped, {d['n_attacks']} kept")
    print(f"benign: {d['n_benign_candidates']} candidates, {d['n_benign_near_duplicates_dropped']} "
          f"near-duplicates dropped, {d['n_benign']} sampled; {d['n_toxic_nonjailbreak_excluded']} "
          f"toxic non-jailbreak prompts excluded from both halves")
    print("FROZEN:", json.dumps(freeze("frozen before any configuration was scored on it; round 7"),
                                 indent=1))
    print("DONE")
