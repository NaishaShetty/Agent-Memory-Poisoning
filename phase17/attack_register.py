"""THE ATTACK REGISTER: every attack population in this project, in one place (round 5).

Written because attacks kept turning up that nothing was tracking. Round 5 alone found that
the `memory_worm` population never implemented its own mechanism, that `sleeper` was being
measured in its dormant condition, that the seven founding families have 24 records between
them, and that BIPIA items were counted as attacks when several are not attacks under any
threat model. Each of those was discovered by accident while looking at something else. A
benchmark that cannot enumerate its own attacks cannot claim coverage.

For every population this records:
  * where it comes from and WHO AUTHORED IT (which model, or which external project, or a
    human) -- the single most load-bearing fact given round 4's authorship finding;
  * how many instances, and how many are valid;
  * whether each instance was validated against its own documented MECHANISM;
  * whether the population has ever been run end-to-end against an undefended agent, i.e.
    whether these attacks are known to DO anything;
  * which evaluations currently report it.

`audit()` prints the register and lists populations with gaps, so an unmeasured attack set is
a visible row rather than an omission.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List

DATA = Path(__file__).parent / "data"
OUT = DATA / "attack_register.json"


def _safe(fn: Callable, default=None):
    try:
        return fn()
    except Exception as exc:  # a missing cache must show as a gap, not crash the register
        return default if default is not None else f"ERROR: {type(exc).__name__}"


def _loaders() -> Dict[str, dict]:
    from phase17.chinese_native_attacks import native_zh_records
    from phase17.corpus_extended import extended_records
    from phase17.external_attacks import external_records
    from phase17.external_test_corpus import test_attack_records
    from phase17.founding_family_regen import founding_regen_records
    from phase17.gemini_authored_attacks import gemini_records
    from phase17.holdout2_corpus import records as mosscap_records
    from phase17.memory_worm_regen import worm_regen_records
    from phase17.novel_attacks import novel_records
    from phase17.novel_attacks_extended import novel_records_extra_only
    from phase17.poison_sets import evasion_records, original_records, regenerated_records
    from phase17.translation import zh_records

    def frozen75():
        from phase17.arenas import frozen_arena

        pools, truth = frozen_arena()
        return [m for p in pools for m in p.memories if m.is_poison_ground_truth]

    return {
        "trackb_original_15": {
            "audit_keys": ("own_trackb_15",),
            "get": original_records, "author": "qwen2.5:7b (Phase 4 reconstructions)",
            "mechanism_validated": False, "note": "the 7 founding families' original records; signals were tuned on these (in-sample)"},
        "trackb_regen_9": {
            "audit_keys": ("own_trackb_regen_9",),
            "get": regenerated_records, "author": "qwen2.5:7b (Phase 11 regeneration)",
            "mechanism_validated": False, "note": "held out from signal design"},
        "founding_regen": {
            "audit_keys": ("own_founding_regen",),
            "get": founding_regen_records, "author": "mistral:7b, validated by llama3.1:8b",
            "mechanism_validated": True, "note": "round 5: enlarges the 7 founding families, which had 24 records total"},
        "novel_60": {
            "audit_keys": ("own_novel_60",),
            "get": novel_records, "author": "qwen2.5:7b",
            "mechanism_validated": False, "note": "6 unseen mechanisms x 10 scenarios"},
        "novel_new120": {
            "audit_keys": ("own_novel_new120",),
            "get": novel_records_extra_only, "author": "qwen2.5:7b",
            "mechanism_validated": False, "note": "scenario-disjoint extension"},
        "memory_worm_regen": {
            "audit_keys": ("own_worm_regen",),
            "get": worm_regen_records, "author": "qwen2.5:7b, validated at generation",
            "mechanism_validated": True, "note": "replaces the original 30 memory_worm instances, which implemented 0/30 of their own mechanism"},
        "gemini_authored_30": {
            "audit_keys": ("own_gemini_30",),
            "get": gemini_records, "author": "gemini (different family)",
            "mechanism_validated": False, "note": "cross-model authorship check"},
        "evasion_47": {
            "audit_keys": ("own_evasion_47",),
            "get": evasion_records, "author": "qwen2.5:7b rewrites of 24 parents",
            "mechanism_validated": False, "note": "fixed-prompt defense-aware rewrites"},
        "zh_translated_84": {
            "audit_keys": ("own_zh_translated_84",),
            "get": zh_records, "author": "qwen2.5:7b translations of English attacks",
            "mechanism_validated": False, "note": "round-trip translation confound; see zh_native_30"},
        "zh_native_30": {
            "audit_keys": ("own_zh_native_30",),
            "get": native_zh_records, "author": "gemini, composed directly in Chinese",
            "mechanism_validated": False, "note": "closes the translation confound"},
        "corpus_extended": {
            "audit_keys": ("own_corpus_extended",),
            "get": extended_records, "author": "qwen2.5:7b",
            "mechanism_validated": False, "note": "extended paraphrase/padding classes"},
        "frozen75_corpus": {
            "audit_keys": ("own_frozen75",),
            "get": frozen75, "author": "Phase 6/12 corpus (qwen2.5:7b)",
            "mechanism_validated": False, "note": "the only arena with coordinated near-duplicate clusters"},
        "external_dev_266": {
            "audit_keys": ("extdev_minja", "extdev_agentpoison", "extdev_injecagent", "extdev_bipia", "extdev_agentdojo"),
            "get": external_records, "author": "MINJA / AgentPoison / InjecAgent / BIPIA / AgentDojo authors",
            "mechanism_validated": False, "note": "external-DEV since round 4 published its per-source results"},
        "external_test_1258": {
            "audit_keys": ("exttest_gandalf", "exttest_deepset"),
            "get": test_attack_records, "author": "HUMAN (Gandalf players) + deepset authors",
            "mechanism_validated": False, "note": "FROZEN test set; 998 of these are human-authored"},
        # ADDED round 6: Mosscap was used as a hold-out and reported in the headline table while
        # appearing in neither this register nor the validity audit, so it had no working-attack
        # denominator at all. That absence is precisely why B14's 91%-vs-54% gap between the two
        # hold-outs could not be tested for composition.
        "holdout2_mosscap_1200": {
            "audit_keys": ("holdout2_mosscap",),
            "get": mosscap_records, "author": "HUMAN (Mosscap players, MIT)",
            "mechanism_validated": False,
            "note": "FROZEN second hold-out, frozen before B15 existed; audited on a seeded "
                    "random 300 of 1,200, so its working rate is an estimate with an interval"},
    }


def build() -> dict:
    from phase17.attack_validity_audit import working_ids

    working = working_ids()
    harm_fams, harm_ids = set(), set()
    for p in (DATA / "harm_study_v2.json", DATA / "harm_study_v2_per_instance.json"):
        if p.exists():
            d = json.loads(p.read_text(encoding="utf-8"))
            for r in d.get("rows", []):
                harm_fams.add(r.get("family"))
                harm_ids.add(r.get("id"))

    rows = []
    for name, spec in _loaders().items():
        recs = _safe(spec["get"], [])
        n = len(recs) if isinstance(recs, list) else 0
        ids = {getattr(r, "scenario_id", None) for r in recs} if n else set()
        rows.append({
            "population": name, "n": n, "author": spec["author"],
            "mechanism_validated_at_generation": spec["mechanism_validated"],
            "audit_keys": list(spec["audit_keys"]),
            "validity_audited": any(k in working for k in spec["audit_keys"]),
            "working_attacks": sum(len(working.get(k, ())) for k in spec["audit_keys"]) or None,
            "harm_measured_instances": len(ids & harm_ids),
            "note": spec["note"],
        })
    gaps = []
    for r in rows:
        if r["n"] == 0:
            gaps.append(f"{r['population']}: NOT BUILT in this checkout (n=0)")
        else:
            if not r["mechanism_validated_at_generation"]:
                gaps.append(f"{r['population']}: instances never checked against their own mechanism")
            if r["harm_measured_instances"] == 0:
                gaps.append(f"{r['population']}: no instance has been run end-to-end against an undefended agent")
    out = {"populations": rows, "total_attack_instances": sum(r["n"] for r in rows), "gaps": gaps}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = build()
    print(f"{'population':22s} {'n':>6s} {'mech?':>6s} {'harm n':>7s}  author")
    for x in r["populations"]:
        print(f"{x['population']:22s} {x['n']:6d} {str(x['mechanism_validated_at_generation']):>6s} "
              f"{x['harm_measured_instances']:7d}  {x['author'][:46]}")
    print(f"\nTOTAL ATTACK INSTANCES: {r['total_attack_instances']}")
    print(f"\nGAPS ({len(r['gaps'])}):")
    for g in r["gaps"]:
        print("  -", g)
    print("DONE")
