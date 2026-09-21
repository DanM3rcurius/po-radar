"""Near-duplicate detection: 3-shingles, MinHash + LSH, union-find clustering.

Identical talking points across outlets are the copypasta signal. Boilerplate is
stripped first so that cookie banners never make two pages look alike.
"""

from __future__ import annotations

import re
from itertools import combinations

from datasketch import MinHash, MinHashLSH

from ..models import Item
from .boilerplate import strip_boilerplate

__all__ = ["shingles", "jaccard", "cluster_items", "uniformity", "minhash"]

_TOKEN_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)

DEFAULT_THRESHOLD = 0.35
DEFAULT_NUM_PERM = 128
# LSH recall margin: candidates are generated below the cut, then confirmed exactly.
CANDIDATE_SLACK = 0.6


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def shingles(text: str, n: int = 3) -> set[str]:
    """Lowercased word n-grams of the de-boilerplated text."""
    if n < 1:
        raise ValueError("shingle size must be >= 1")
    words = _tokens(strip_boilerplate(text))
    if not words:
        return set()
    if len(words) < n:
        return {" ".join(words)}
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Exact Jaccard similarity of two shingle sets."""
    if not a and not b:
        return 0.0
    union = len(a | b)
    if not union:
        return 0.0
    return len(a & b) / union


def minhash(grams: set[str], num_perm: int = DEFAULT_NUM_PERM) -> MinHash:
    """Deterministic MinHash sketch of a shingle set (fixed seed)."""
    sketch = MinHash(num_perm=num_perm)
    for gram in sorted(grams):
        sketch.update(gram.encode("utf-8"))
    return sketch


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # Always attach the larger root to the smaller: keeps ordering stable.
            if ra < rb:
                self._parent[rb] = ra
            else:
                self._parent[ra] = rb


def cluster_items(
    items: list[Item],
    threshold: float = DEFAULT_THRESHOLD,
    num_perm: int = DEFAULT_NUM_PERM,
) -> list[list[Item]]:
    """Group near-duplicate items. Singletons are returned as one-item clusters.

    MinHashLSH is a recall device: it is built at a deliberately looser
    threshold (``threshold * CANDIDATE_SLACK``) so that pairs sitting just under
    the banding curve still surface, and every candidate pair is then confirmed
    against the exact Jaccard of its shingle sets. That keeps ``threshold`` an
    honest cut rather than a probabilistic one.

    Ordering is deterministic: clusters are ordered by the position of their
    first member in `items`, and members keep their input order.
    """
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")
    if not items:
        return []
    if len(items) == 1:
        return [[items[0]]]

    grams = [shingles(it.text) for it in items]
    sketches = [minhash(g, num_perm=num_perm) for g in grams]
    lsh = MinHashLSH(threshold=max(0.05, threshold * CANDIDATE_SLACK), num_perm=num_perm)
    for idx, sketch in enumerate(sketches):
        lsh.insert(str(idx), sketch)

    uf = _UnionFind(len(items))
    for idx, sketch in enumerate(sketches):
        for key in sorted(lsh.query(sketch), key=int):
            other = int(key)
            if other <= idx:
                continue
            if jaccard(grams[idx], grams[other]) >= threshold:
                uf.union(idx, other)

    groups: dict[int, list[Item]] = {}
    order: list[int] = []
    for idx, item in enumerate(items):
        root = uf.find(idx)
        if root not in groups:
            groups[root] = []
            order.append(root)
        groups[root].append(item)
    return [groups[root] for root in order]


def uniformity(texts: list[str]) -> float:
    """Mean pairwise Jaccard of 3-shingles. Zero for fewer than two texts."""
    if len(texts) < 2:
        return 0.0
    grams = [shingles(t) for t in texts]
    pairs = list(combinations(range(len(grams)), 2))
    if not pairs:
        return 0.0
    total = sum(jaccard(grams[i], grams[j]) for i, j in pairs)
    return total / len(pairs)
