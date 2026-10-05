"""Scoring the founding families WITH corroboration evidence supplied (round 6 gap fix).

THE PROBLEM, and it is a reporting defect of mine rather than a defense weakness. `eval_round6`
passes `sources` but never `evidence`, so B13's NLI corroboration -- the signal that reaches
additive fabrication (0/72 to 37/72, pre-registered) -- is INERT in every table this project
produced from it. That is why B12 and B13 are byte-identical on all seven founding families
there, and why `sleeper_memory_poisoning` reads 0% under every configuration. Round 5 knew this
and said so (`evidence_available_check.py` calls those numbers a floor); I failed to carry the
caveat into the round-6 reporting, where it reads as a flat detection failure.

`evidence_available_check` measured the gap on three populations and found B13 on `evasion_47`
going 4/47 to 28/47 with the real conversation supplied (p<0.0001). This module extends that to
every own-attack population, per attack family, with the two things that comparison needs to be
honest:

  1. THE SAME EVIDENCE IS GIVEN TO THE BENIGN POPULATIONS. Supplying an owner conversation makes
     every claim about a person who does not appear in it uncorroborated -- which is real signal
     against an invented-persona attack, and equally a real risk to a benign note about someone
     the conversation never mentions. Reporting the recall gain without the false-positive cost
     measured on the same footing would be meaningless, so both arms are run and reported
     together. If the false-positive rate rises as much as recall, there is no gain and this
     module says so.
  2. THE EVIDENCE IS THE REAL CONVERSATION'S OWN TURNS, not anything constructed for the test,
     and the poison is marked as arriving on an untrusted channel exactly as the threat model
     states.

WHAT THIS CANNOT FIX, stated up front. The external injection corpora have no owner
conversation: their attacks are not claims about a person, so there is nothing to corroborate
and evidence is not applicable. Their numbers are unaffected by design, and B13's weakness on
them is genuine rather than an artifact.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence

OUT = Path(__file__).parent / "data" / "evidence_round6.json"
PARTIAL = Path(__file__).parent / "data" / "evidence_round6_partial.json"
CONFIGS = ("B12", "B13", "B14", "B15", "B17", "B18")
BATCH = 4
LOCOMO_SAMPLE = 0
# Populations whose texts are the USER'S OWN WORDS. Scoring these as `tool_output` asks the
# wrong question: a legitimate standing instruction arriving from a tool output SHOULD be
# flagged, and this project's 2/40 headline for legitimate instructions was measured in the
# user_turn condition. Scoring them only as tool_output made the corroboration fix look like a
# regression on that metric (2/40 -> 18/40) when the two numbers describe different channels.
USER_TURN_POPS = ("legitimate_imperatives_40", "named_party_preferences_6", "confirmed_human_20")


def _evidence():
    """The real conversation's own turns, plus the speaker names the rule needs."""
    from phase17.provenance_sets import owner_turns

    turns = owner_turns(LOCOMO_SAMPLE)
    names = sorted({t.get("speaker") for t in turns if t.get("speaker")})
    return [t["text"] for t in turns], names


def _decide(cfg: str, items, evidence, names, source="tool_output"):
    from phase14.defended_retrieval import apply_defense

    src = {mid: source for mid, _ in items}
    ctx = dict(sources=src, evidence=evidence, evidence_names=names) if cfg != "B12" else {}
    _, dec = apply_defense(cfg, tuple(items), **ctx)
    return [bool(d.excluded) for d in dec]


def _score(cfg, texts: Sequence[str], prefix: str, evidence, names, key: str, done: dict,
           source: str = "tool_output"):
    """Checkpointed, within-population, so a long run resumes."""
    out = list(done.get(key, []))
    start = (len(out) // BATCH) * BATCH
    out = out[:start]
    for i in range(start, len(texts), BATCH):
        chunk = [(f"{prefix}-{i+j}", t) for j, t in enumerate(texts[i:i + BATCH])]
        out += _decide(cfg, chunk, evidence, names, source)
        if (i // BATCH) % 20 == 0:
            done[key] = out
            PARTIAL.write_text(json.dumps(done), encoding="utf-8")
            print(f"    {cfg} {prefix} {len(out)}/{len(texts)}", flush=True)
    done[key] = out
    PARTIAL.write_text(json.dumps(done), encoding="utf-8")
    return out


def run(configs=CONFIGS) -> dict:
    from phase17.eval_populations import benign_populations
    from phase17.eval_round6 import _attack_pops
    from phase17.stats import paired_delta, rate_with_ci

    ev, names = _evidence()
    print(f"evidence: {len(ev)} real conversation turns, speakers {names}", flush=True)
    attacks = {k: v for k, v in _attack_pops().items() if k.startswith("own_")}
    benign = {k: list(v) for k, v in benign_populations().items()}
    r6 = json.loads((Path(__file__).parent / "data" / "eval_round6.json").read_text(encoding="utf-8"))
    done = json.loads(PARTIAL.read_text(encoding="utf-8")) if PARTIAL.exists() else {}

    # family membership, so the founding families can be reported by name
    fam_of: Dict[str, List[tuple]] = {}
    for pop, recs in attacks.items():
        for i, r in enumerate(recs):
            fam_of.setdefault(r.family, []).append((pop, i))

    with_ev: Dict[str, Dict[str, List[bool]]] = {c: {} for c in configs}
    for c in configs:
        for pop, recs in attacks.items():
            with_ev[c][pop] = _score(c, [r.text for r in recs], f"EV-{pop}", ev, names,
                                     f"{c}:atk:{pop}", done)
        for pop, texts in benign.items():
            with_ev[c][f"benign::{pop}"] = _score(c, texts, f"EVB-{pop}", ev, names,
                                                  f"{c}:ben:{pop}", done)
        # The same user-authored populations in their REAL channel, where provenance trusts them.
        for pop in USER_TURN_POPS:
            if pop in benign:
                with_ev[c][f"benign::{pop} [as user_turn]"] = _score(
                    c, benign[pop], f"EVU-{pop}", ev, names, f"{c}:benu:{pop}", done,
                    source="user_turn")
        print(f"  {c} done", flush=True)

    def no_ev(c, pop):
        return [bool(e) for e, _ in r6["raw"][c][f"attack::{pop}"]] if c in r6["raw"] else None

    def no_ev_b(c, pop):
        k = f"benign::{pop}"
        return [bool(e) for e, _ in r6["raw"][c][k]] if c in r6["raw"] and k in r6["raw"][c] else None

    out = {"evidence_turns": len(ev), "speakers": names, "configs": list(configs),
           "note": "own-attack populations only; the external corpora have no owner conversation "
                   "and nothing to corroborate, so evidence is not applicable there",
           "by_family": {}, "by_population": {}, "benign": {}}

    for fam, members in sorted(fam_of.items()):
        e = {"n": len(members)}
        for c in configs:
            w = [with_ev[c][p][i] for p, i in members if i < len(with_ev[c].get(p, []))]
            n_ = []
            for p, i in members:
                v = no_ev(c, p)
                if v and i < len(v):
                    n_.append(v[i])
            if not w or len(w) != len(n_):
                continue
            e[c] = {"no_evidence": rate_with_ci(sum(n_), len(n_)),
                    "with_evidence": rate_with_ci(sum(w), len(w)),
                    "paired": paired_delta(w, n_)}
        out["by_family"][fam] = e

    for pop in attacks:
        e = {"n": len(attacks[pop])}
        for c in configs:
            w, n_ = with_ev[c].get(pop), no_ev(c, pop)
            if w and n_ and len(w) == len(n_):
                e[c] = {"no_evidence": rate_with_ci(sum(n_), len(n_)),
                        "with_evidence": rate_with_ci(sum(w), len(w)),
                        "paired": paired_delta(w, n_)}
        out["by_population"][pop] = e

    ordinary = [p for p in benign if any(s in p for s in ("dataset_arena", "convomem", "perltqa"))]
    # Report the user_turn variants too. They were computed above but an earlier version of
    # this loop iterated only `benign`, so the arm that answers the legitimate-instruction
    # question existed on disk and never reached the artifact.
    benign_keys = list(benign) + [f"{p} [as user_turn]" for p in USER_TURN_POPS if p in benign]
    for pop in benign_keys:
        base = pop.replace(" [as user_turn]", "")
        e = {"n": len(benign[base]), "ordinary": pop in ordinary,
             "channel": "user_turn" if "[as user_turn]" in pop else "tool_output"}
        for c in configs:
            w, n_ = with_ev[c].get(f"benign::{pop}"), no_ev_b(c, pop)
            if w is not None:
                e[c] = {"with_evidence": rate_with_ci(sum(w), len(w))}
                if n_ and len(n_) == len(w):
                    e[c]["no_evidence"] = rate_with_ci(sum(n_), len(n_))
                    e[c]["paired"] = paired_delta(w, n_)
        out["benign"][pop] = e

    # The headline pair: aggregate own-attack recall and ordinary-benign FPR, both arms.
    out["aggregate"] = {}
    for c in configs:
        aw = [x for p in attacks for x in with_ev[c].get(p, [])]
        an = [x for p in attacks for x in (no_ev(c, p) or [])]
        bw = [x for p in ordinary for x in with_ev[c].get(f"benign::{p}", [])]
        bn = [x for p in ordinary for x in (no_ev_b(c, p) or [])]
        out["aggregate"][c] = {
            "attacks_no_evidence": rate_with_ci(sum(an), len(an)) if an else None,
            "attacks_with_evidence": rate_with_ci(sum(aw), len(aw)) if aw else None,
            "ordinary_benign_no_evidence": rate_with_ci(sum(bn), len(bn)) if bn else None,
            "ordinary_benign_with_evidence": rate_with_ci(sum(bw), len(bw)) if bw else None,
        }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    r = run()
    FOUNDING = ("agentpoison", "minja", "farma", "memorygraft", "dsrm", "mpbench",
                "sleeper_memory_poisoning")
    print("\n### FOUNDING FAMILIES: no evidence -> with evidence")
    for f in FOUNDING:
        v = r["by_family"].get(f)
        if not v:
            print(f"  {f:26s} absent")
            continue
        cells = []
        for c in r["configs"]:
            if c in v:
                cells.append(f"{c} {v[c]['no_evidence']['k']:3d}->{v[c]['with_evidence']['k']:<3d}"
                             f"(p={v[c]['paired']['p_exact']:.3g})")
        print(f"  {f:26s} n={v['n']:3d}  " + "  ".join(cells))
    print("\n### AGGREGATE (own attacks / ordinary benign)")
    for c, v in r["aggregate"].items():
        a0, a1 = v["attacks_no_evidence"], v["attacks_with_evidence"]
        b0, b1 = v["ordinary_benign_no_evidence"], v["ordinary_benign_with_evidence"]
        if a0 and a1:
            print(f"  {c}: attacks {a0['rate']:.1%} -> {a1['rate']:.1%}   "
                  f"benign FPR {(b0['k'] if b0 else '-')}/{b0['n'] if b0 else '-'} -> "
                  f"{b1['k'] if b1 else '-'}/{b1['n'] if b1 else '-'}")
    print("DONE")
