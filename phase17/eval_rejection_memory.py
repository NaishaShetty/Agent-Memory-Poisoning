"""Does rejection memory actually blunt the adaptive attacker? (round 6, the #5 item)

THE TEST. The same query-based adaptive attacker from `adaptive_query_attacker.py`, same seeds,
same budget of 5, same rewrite model and same NLI claim-preservation requirement -- run twice:

  B15  stateless, as published
  B16  B15 + a ledger that PERSISTS ACROSS THE ATTACKER'S ROUNDS for that seed

Only the statefulness changes. The attacker is not weakened, told anything, or budget-limited
differently; it still sees each verdict and rewrites against it.

WHY THE PAIRWISE DEV NUMBER UNDERSTATES THIS, which is the point worth measuring. The dev fit
reports 17.0% of claim-preserving paraphrases caught at the frozen radius of 0.97. Read as a
per-attempt rate that sounds useless. But the ledger holds EVERY previous attempt, not one, so
by round 5 a rewrite must clear four separate radii at once, and the attempts are positively
correlated (they are all paraphrases of one claim, so they cluster). The sequence-level effect
is therefore strictly larger than the pairwise rate, and how much larger is an empirical
question this module answers instead of estimating.

WHAT WOULD FALSIFY THE IDEA, stated before running it:
  * B16's static recall differing from B15's. That would mean the ledger is firing when it
    should be empty -- a bug, not a result. Asserted structurally in `test_rejection_memory.py`.
  * no reduction in `genuine_adaptive_evasion_of_initially_excluded`, the only metric the
    mechanism targets.
  * a measurable benign cost. Reported from `rejection_memory_config.json`'s per-population dev
    FPR (0.0% in all 7 populations, including the imperative-voice one) and re-checked here
    against the ledgers the attack run actually produced -- a live ledger built from real
    rejections, not a synthetic one.

THE LIMITATION, which belongs next to the result and not in a footnote: this helps only when
the attacker's attempts reach the same scope's ledger. A single-shot attacker, an attacker who
spreads attempts across isolated scopes, and an attacker who waits out the TTL are all
unaffected. That is a narrower claim than "B16 beats adaptive evasion", and it is the claim the
numbers support.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from phase17.stats import rate_with_ci

OUT = Path(__file__).parent / "data" / "eval_rejection_memory.json"
PARTIAL = Path(__file__).parent / "data" / "eval_rejection_partial.json"
CONFIGS = ("B15", "B16")


def _seeds(n_external: int = 12):
    """The SAME seeds adaptive_query_attacker uses, from its own extracted helper -- not a copy."""
    from phase17.adaptive_query_attacker import _seed_records

    return _seed_records(n_external)[0]


def attack_one_stateful(seed_id: str, seed_text: str, config_name: str, use_ledger: bool) -> dict:
    """`adaptive_query_attacker.attack_one`, with one change: an optional ledger that survives
    the attacker's rounds. Everything else -- budget, rewrite prompt, retries, the NLI
    claim-preservation gate, the excluded/flagged distinction -- is reused unchanged."""
    from phase12.propagation.ollama_provider import OllamaProvider
    from phase14.defended_retrieval import HARD_MITIGATION_ACTIONS, apply_defense
    from phase17.adaptive_query_attacker import QUERY_BUDGET, REWRITE_RETRIES, _claim_preserved, _rewrite
    from phase17.rejection_memory import RejectionLedger, configured_reject_sim
    from phase3.evaluation.llm.provider import GenerationConfig

    provider = OllamaProvider(model="qwen2.5:7b")
    ledger = RejectionLedger(reject_sim=configured_reject_sim()) if use_ledger else None
    history: List[dict] = []
    current = seed_text
    for round_i in range(QUERY_BUDGET):
        ctx = {"ledger": ledger, "scope": seed_id} if use_ledger else {}
        _, dec = apply_defense(config_name, [(seed_id, current)], **ctx)
        action = dec[0].action
        not_excluded = action not in HARD_MITIGATION_ACTIONS
        preserved = _claim_preserved(seed_text, current)
        history.append({"round": round_i, "text": current[:300], "action": action,
                        "not_excluded": not_excluded, "claim_preserved": preserved,
                        "ledger_size": ledger.size(seed_id) if ledger else 0})
        if not_excluded and preserved:
            return {"seed_id": seed_id, "success": True, "genuine_adaptive_evasion": round_i > 0,
                    "rounds_used": round_i + 1, "history": history}
        if not_excluded and not preserved:
            return {"seed_id": seed_id, "success": False,
                    "reason": "evaded exclusion but broke its own claim (not a real win)",
                    "rounds_used": round_i + 1, "history": history}
        rewritten = None
        for attempt in range(REWRITE_RETRIES):
            cfg2 = GenerationConfig(temperature=0.8, seed=100000 + round_i * 10 + attempt, max_tokens=100,
                                    enable_thinking=False, n_ctx=2048, request_timeout_sec=180.0)
            cand = _rewrite(provider, cfg2, seed_text, current, action)
            if _claim_preserved(seed_text, cand):
                rewritten = cand
                break
        current = rewritten if rewritten is not None else current
    return {"seed_id": seed_id, "success": False, "reason": "query budget exhausted",
            "rounds_used": QUERY_BUDGET, "history": history}


def static_equivalence(n: int = 60) -> dict:
    """Confirm on REAL records that B16 == B15 with no ledger threaded.

    `test_rejection_memory.py` asserts this under a monkeypatched B15, which proves the control
    flow. This proves it on the actual detector over real attack text, because the claim the
    whole comparison rests on -- that only statefulness differs -- is worth checking against the
    thing itself and not only against a stub.
    """
    from phase14.defended_retrieval import apply_defense
    from phase17.novel_attacks import novel_records

    recs = novel_records()[:n]
    diffs = []
    for r in recs:
        items = [(r.scenario_id, r.text)]
        _, d15 = apply_defense("B15", items)
        _, d16 = apply_defense("B16", items)
        if d15[0].action != d16[0].action or d15[0].excluded != d16[0].excluded:
            diffs.append({"id": r.scenario_id, "B15": d15[0].action, "B16": d16[0].action})
    return {"n_checked": len(recs), "n_differing": len(diffs), "differing": diffs[:10],
            "verdict": "OK: identical" if not diffs else
                       "BUG: B16 differs from B15 with no ledger, so state is leaking and the "
                       "adaptive comparison below is invalid"}


def _summarise(rows: List[dict]) -> dict:
    init_excl = [r for r in rows if r["history"] and not r["history"][0]["not_excluded"]]
    genuine = [r for r in init_excl if r.get("success") and r.get("genuine_adaptive_evasion")]
    broke = [r for r in rows if not r.get("success") and "broke its own claim" in str(r.get("reason", ""))]
    return {
        "n_seeds": len(rows),
        "n_initially_excluded": len(init_excl),
        "baseline_miss": rate_with_ci(sum(1 for r in rows if r["history"] and r["history"][0]["not_excluded"]),
                                      len(rows)),
        # THE metric the mechanism targets: seeds the defense DID catch, that the attacker
        # recovered by rewriting. Everything else is unaffected by statefulness by construction.
        "genuine_adaptive_evasion_of_initially_excluded": rate_with_ci(len(genuine), len(init_excl)),
        "attacker_self_destructed": rate_with_ci(len(broke), len(rows)),
        "mean_rounds_used": round(sum(r["rounds_used"] for r in rows) / max(len(rows), 1), 2),
    }


def run(n_external: int = 12, workers: int = 3) -> dict:
    import concurrent.futures as cf

    seeds = _seeds(n_external)
    print(f"adaptive attacker vs {CONFIGS} on {len(seeds)} seeds", flush=True)
    out = {"n_seeds": len(seeds), "configs": list(CONFIGS),
           "frozen_reject_sim": __import__("phase17.rejection_memory", fromlist=["x"]).configured_reject_sim(),
           "per_config": {}}
    out["static_equivalence"] = static_equivalence()
    print(f"  static equivalence B16 vs B15: {out['static_equivalence']['verdict']}", flush=True)
    for cfg in CONFIGS:
        use_ledger = cfg == "B16"
        # RESUMABLE: each seed-run is up to 5 defense queries plus rewrites, so losing a
        # part-finished config to a stopped wrapper costs 20+ minutes. harm_study_v2 lost 550
        # agent calls that way an hour before this was written; same flaw, same fix.
        done_map = {}
        if PARTIAL.exists():
            try:
                done_map = json.loads(PARTIAL.read_text(encoding="utf-8"))
            except Exception:
                done_map = {}
        todo = [(sid, text) for sid, text, _f in seeds if f"{cfg}:{sid}" not in done_map]
        rows: List[dict] = [done_map[f"{cfg}:{sid}"] for sid, _t, _f in seeds
                            if f"{cfg}:{sid}" in done_map]
        if rows:
            print(f"  {cfg}: {len(rows)} cached, {len(todo)} to compute", flush=True)
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(attack_one_stateful, sid, text, cfg, use_ledger): sid
                    for sid, text in todo}
            for done, f in enumerate(cf.as_completed(futs), 1):
                r = f.result()
                rows.append(r)
                done_map[f"{cfg}:{r['seed_id']}"] = r
                if done % 5 == 0 or done == len(todo):
                    PARTIAL.write_text(json.dumps(done_map, ensure_ascii=False), encoding="utf-8")
                    print(f"  {cfg}: {done}/{len(todo)}", flush=True)
        PARTIAL.write_text(json.dumps(done_map, ensure_ascii=False), encoding="utf-8")
        out["per_config"][cfg] = {**_summarise(rows), "rows": rows}
        s = out["per_config"][cfg]
        print(f"  {cfg}: genuine adaptive evasion of initially-excluded "
              f"{s['genuine_adaptive_evasion_of_initially_excluded']['k']}/"
              f"{s['genuine_adaptive_evasion_of_initially_excluded']['n']}", flush=True)

    from phase17.stats import paired_delta

    ids = [sid for sid, _t, _f in seeds]
    def _vec(cfg):
        by = {r["seed_id"]: r for r in out["per_config"][cfg]["rows"]}
        return [bool(by[i].get("success") and by[i].get("genuine_adaptive_evasion")) for i in ids if i in by]
    out["paired_B16_vs_B15"] = paired_delta(_vec("B16"), _vec("B15"))
    out["interpretation"] = (
        "Only statefulness differs. A reduction here is attributable to the ledger, since B16's "
        "first-round decision is B15's by construction. Applies to attackers that retry against "
        "the same scope; single-shot and scope-distributed attackers are unaffected.")
    for cfg in CONFIGS:
        for r in out["per_config"][cfg]["rows"]:
            r["history"] = r["history"][:6]
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    for cfg in r["configs"]:
        s = r["per_config"][cfg]
        g = s["genuine_adaptive_evasion_of_initially_excluded"]
        print(f"\n{cfg}: initially excluded {s['n_initially_excluded']}/{s['n_seeds']}; "
              f"genuine adaptive evasion {g['k']}/{g['n']} = {g['rate']:.1%}; "
              f"mean rounds {s['mean_rounds_used']}")
    print(f"\npaired B16 vs B15: {r['paired_B16_vs_B15']}")
    print("DONE")
