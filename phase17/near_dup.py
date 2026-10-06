"""Near-duplicate detection between corpora, so a new hold-out cannot quietly contain text the
project has already seen.

WHY. Hold-out 3 was asserted disjoint from its dev snapshot by EXACT text match, and 110 exact
overlaps were found and dropped. Exact match is the weak form of that check: jailbreak prompts
circulate as lightly edited copies ("DAN 6.0", "DAN 6.2", a name swapped, a sentence appended),
so two corpora can share no identical string while sharing most of their content. A hold-out
that contains a near-copy of a dev item measures memorisation of that item, not generalisation.

The measure is word 5-gram CONTAINMENT, |A & B| / min(|A|, |B|), not Jaccard: a short prompt
quoted inside a long one is a duplicate for this purpose even though their Jaccard is small.
The threshold is fixed here, before any corpus it is applied to was built, and is not tuned.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Set, Tuple

N = 5
THRESHOLD = 0.6
_WS = re.compile(r"[^\w]+", re.UNICODE)
# The wrappers every external corpus here is placed into memory with. They are shared
# boilerplate, so they are stripped before comparison or every item would match every other.
_WRAPPER_PREFIXES = ("saved from a tool result:", "note from a document the user shared:",
                     "reminder for future sessions:")


def _norm(t: str) -> List[str]:
    t = t.strip().lower()
    for p in _WRAPPER_PREFIXES:
        if t.startswith(p):
            t = t[len(p):]
            break
    return [w for w in _WS.split(t) if w]


def shingles(t: str, n: int = N) -> Set[Tuple[str, ...]]:
    w = _norm(t)
    if len(w) < n:
        return {tuple(w)} if w else set()
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


class Index:
    """An inverted index over shingles of a reference collection."""

    def __init__(self, texts: Iterable[str]):
        self.sh: List[Set[Tuple[str, ...]]] = []
        self.inv: Dict[Tuple[str, ...], List[int]] = defaultdict(list)
        for i, t in enumerate(texts):
            s = shingles(t)
            self.sh.append(s)
            for g in s:
                self.inv[g].append(i)

    def max_containment(self, t: str) -> float:
        s = shingles(t)
        if not s:
            return 0.0
        hits: Dict[int, int] = defaultdict(int)
        for g in s:
            for j in self.inv.get(g, ()):
                hits[j] += 1
        best = 0.0
        for j, k in hits.items():
            d = min(len(s), len(self.sh[j])) or 1
            best = max(best, k / d)
        return best


def split_near_duplicates(candidates: Sequence[str], reference: Iterable[str],
                          threshold: float = THRESHOLD) -> Tuple[List[int], List[int]]:
    """Return (indices kept, indices dropped as near-duplicates of the reference)."""
    idx = Index(reference)
    keep, drop = [], []
    for i, t in enumerate(candidates):
        (drop if idx.max_containment(t) >= threshold else keep).append(i)
    return keep, drop
