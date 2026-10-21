"""HO11 owner pool (v8 W3; docs/phase17/v8/V8_PREREG_ADDENDUM_W3.md).

Fresh propagation-root owners, never used by ANY prior HO round (HO4=LoCoMo sample 7,
HO7=sample 8, HO8=sample 1, HO9=samples 2/3/5/9, HO10=samples 0/4/6 -- all 10 LoCoMo
samples are now used for propagation roots) and never used by SA-8 either (owners
100-109): 9 Conversation Chronicles episodes immediately following SA-8's 10 in the same
deterministic candidate ordering (phase17.defence_v8.cc_owners.select_owner_episodes),
so the selection rule is identical, just continuing where SA-8 left off. Owner ids
110-118.
"""
from __future__ import annotations

from typing import Dict, List

from phase17.defence_v8.cc_owners import OWNER_EPISODE as _SA8_EPISODES
from phase17.defence_v8.cc_owners import _episode_turns, select_owner_episodes

OWNERS = tuple(range(110, 119))

# Frozen owner -> CC conversation_id mapping: the first 9 candidates from
# select_owner_episodes(n=25) not already used by SA-8.
OWNER_EPISODE: Dict[int, str] = {
    110: "episode-100258",
    111: "episode-100266",
    112: "episode-100272",
    113: "episode-10030",
    114: "episode-100305",
    115: "episode-100326",
    116: "episode-100354",
    117: "episode-100357",
    118: "episode-10038",
}

# D-V8-6 (docs/phase17/v8/IMPLEMENTATION_NOTES.md): CC's generic role labels ("Classmates
# A", "Mentee", ...) are reproduced almost never by mistral:7b-text's RAW completion (no
# instruction-following, unlike Gemini's SA-8/SA-9 generation, which was directly told to
# name "{who}"): 77/80 of the first HO11 generation attempts failed their own-name gate
# after all 6 retries. Fixed by substituting natural fictional first names for the role
# labels -- in the context excerpt AND the gate/prompt, consistently -- so the base model
# sees and continues ordinary name text throughout, exactly as HO9/HO10's real LoCoMo
# names (Evan, Sam, Deborah, ...) let it do. Names are fictional, assigned per owner,
# independent of any family/kind (same label-independence discipline as writer_policy).
NATURAL_NAMES: Dict[int, tuple] = {
    110: ("Priya", "Marcus"),
    111: ("Owen", "Leah"),
    112: ("Darius", "Nina"),
    113: ("Tomas", "Ingrid"),
    114: ("Aisha", "Felix"),
    115: ("Rosa", "Kenji"),
    116: ("Liam", "Sade"),
    117: ("Noor", "Victor"),
    118: ("Greta", "Amir"),
}


def _reselect(n: int = 25) -> List[str]:
    """Reproduces OWNER_EPISODE's selection: the fresh candidates (not in SA-8's set)
    from the same deterministic ordering, in order."""
    cands = select_owner_episodes(n=n)
    used = set(_SA8_EPISODES.values())
    return [c for c in cands if c not in used]


_CACHE: Dict[int, List[dict]] = {}


def _rows_cached(owner: int) -> List[dict]:
    """ho11_owners.OWNER_EPISODE's 9 episodes are read from the 1GB memory_records.jsonl
    once per owner per process and cached -- cc_owners/longmemeval_owners's own
    per-call full-file scan is fine at their single-digit call volume (corpus generation
    calls each owner once or twice), but ho11_corpus.build()/flags()/ho11_chains.chains()
    all call owner_turns per owner repeatedly across their own loops, so this module adds
    the cache the others did not need."""
    if owner not in _CACHE:
        _CACHE[owner] = _episode_turns(OWNER_EPISODE[owner])
    return _CACHE[owner]


def _role_to_name_map(owner: int) -> Dict[str, str]:
    """role label (in encounter order) -> this owner's natural fictional name, consistent
    with speakers(owner)'s own ordering."""
    rows = _rows_cached(owner)
    roles = []
    for r in rows:
        if r["source_role"] not in roles:
            roles.append(r["source_role"])
    names = NATURAL_NAMES[owner]
    return dict(zip(roles[:2], names))


def speakers(owner: int) -> List[str]:
    """Natural fictional names (D-V8-6), not the raw CC role labels."""
    return list(NATURAL_NAMES[owner])


def owner_turns(owner: int) -> List[Dict]:
    """Context excerpt text uses the natural names throughout (not the raw role labels),
    so a base completion model sees and continues ordinary name text."""
    rows = _rows_cached(owner)
    role_to_name = _role_to_name_map(owner)
    out = []
    for r in rows:
        name = role_to_name.get(r["source_role"], r["source_role"])
        out.append({"dia_id": r["memory_id"], "speaker": name, "text": f"{name}: {r['content']}"})
    return out
