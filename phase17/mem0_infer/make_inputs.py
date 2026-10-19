"""Export the inputs for the Mem0 (infer=True) experiments MEM-1 and MEM-2 to JSON, so the isolated mem0venv
interpreter needs only mem0 + json. Main environment:  python -m phase17.mem0_infer.make_inputs"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "mem0_infer" / "inputs.json"
N_BASE = 100
BATCH = 10


def run() -> dict:
    from phase17.holdout4_corpus import attack_records, benign_texts, verify_frozen
    from phase17.holdout4_validity import _tasks
    from phase17.provenance_sets import owner_turns
    from phase17.remediation.sleeper_corpus import items, verify_frozen as sa_frozen

    assert verify_frozen() and sa_frozen()
    recs = attack_records()
    tasks = _tasks("v2", recs)                         # cached non-leading probe tasks (HO4 causal audit, v2)
    owners = {}
    for s in (7, 3):
        turns = [t["text"] for t in owner_turns(s)[:N_BASE]]
        owners[str(s)] = [turns[i:i + BATCH] for i in range(0, len(turns), BATCH)]
    data = {
        "owners": owners,
        "ho4": {"owner": "7",
                "attacks": [{"id": r.scenario_id, "family": r.family, "text": r.text, "task": tasks[r.scenario_id]}
                            for r in recs],
                "benign": [{"id": f"HO4B-{i}", "text": t} for i, t in enumerate(benign_texts())]},
        "sa1": {"owner": "3",
                "items": [{"id": x["id"], "kind": k, "text": x["note"], "trigger": x["trigger"],
                           "non_trigger": x["non_trigger"]} for k in ("atk", "ben") for x in items(k)]},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"ho4_attacks": len(data["ho4"]["attacks"]), "ho4_benign": len(data["ho4"]["benign"]),
            "sa1": len(data["sa1"]["items"])}


if __name__ == "__main__":
    print(run())
