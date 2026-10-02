"""Exact and near-duplicate detection.

Near duplicates use multi-index hashing: with a Hamming threshold t, two 64-bit hashes
within distance t must agree exactly on at least one of t+1 disjoint bit chunks
(pigeonhole). So we bucket by each chunk and only compare hashes that share a bucket,
with vectorised popcounts. Identical hashes are collapsed first so clusters of exact
copies don't explode into n^2 pairs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

BLOCK = 2048  # max rows per pairwise block


@dataclass
class DupResult:
    rows: pd.Index  # df index labels of the rows analysed (positional order below)
    exact_groups: list[np.ndarray]  # positions of byte-identical files, size >= 2
    near_pairs: np.ndarray  # (k, 3): position a, position b, Hamming distance (a < b)
    component: np.ndarray  # component id per position, -1 = no near duplicate
    n_components: int

    def component_members(self) -> list[np.ndarray]:
        out = []
        for cid in range(self.n_components):
            out.append(np.flatnonzero(self.component == cid))
        return out


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = np.arange(n)

    def find(self, x: int) -> int:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _chunks(threshold: int) -> list[tuple[int, int]]:
    n = threshold + 1
    widths = [64 // n + (1 if i < 64 % n else 0) for i in range(n)]
    out, shift = [], 0
    for w in widths:
        out.append((shift, w))
        shift += w
    return out


def near_pairs_unique(hashes: np.ndarray, threshold: int) -> np.ndarray:
    """Pairs (i, j, d) with i < j among *distinct* uint64 hashes where popcount(h_i ^ h_j) <= t."""
    n = len(hashes)
    if n < 2:
        return np.empty((0, 3), dtype=np.int64)
    found: list[np.ndarray] = []
    for shift, width in _chunks(threshold):
        mask = np.uint64((1 << width) - 1)
        keys = (hashes >> np.uint64(shift)) & mask
        order = np.argsort(keys, kind="stable")
        sorted_keys = keys[order]
        bounds = np.flatnonzero(np.diff(sorted_keys)) + 1
        starts = np.concatenate([[0], bounds])
        ends = np.concatenate([bounds, [n]])
        for s, e in zip(starts, ends, strict=True):
            if e - s < 2:
                continue
            idx = order[s:e]
            for bs in range(0, len(idx), BLOCK):
                a_idx = idx[bs : bs + BLOCK]
                b_idx = idx[bs:]
                d = np.bitwise_count(hashes[a_idx][:, None] ^ hashes[b_idx][None, :])
                ai, bi = np.nonzero(d <= threshold)
                keep = (bs + ai) < (bs + bi)  # upper triangle within the bucket
                if keep.any():
                    i, j = a_idx[ai[keep]], b_idx[bi[keep]]
                    lo, hi = np.minimum(i, j), np.maximum(i, j)
                    found.append(np.stack([lo, hi, d[ai[keep], bi[keep]]], axis=1))
    if not found:
        return np.empty((0, 3), dtype=np.int64)
    pairs = np.concatenate(found).astype(np.int64)
    _, first = np.unique(pairs[:, 0] * n + pairs[:, 1], return_index=True)
    return pairs[np.sort(first)]


def find_duplicates(df: pd.DataFrame, threshold: int, exclude: pd.Series | None = None) -> DupResult:
    """`df` holds readable rows with sha256 and phash. `exclude` marks rows skipped for near-dups
    (e.g. blank images, which all share one hash)."""
    n = len(df)
    sha = df["sha256"].to_numpy()
    exact_groups = [
        np.asarray(pos) for pos in pd.Series(np.arange(n)).groupby(sha).groups.values()
        if len(pos) > 1
    ]

    uf = _UnionFind(n)
    near_mask = np.ones(n, dtype=bool) if exclude is None else ~exclude.to_numpy(dtype=bool)
    pos = np.flatnonzero(near_mask)
    pair_list: list[np.ndarray] = []
    if len(pos) > 1:
        hashes = np.array([int(h) for h in df["phash"].to_numpy()[pos]], dtype=np.uint64)
        uniq, inverse = np.unique(hashes, return_inverse=True)
        # identical hashes: chain members together, pairs at distance 0
        members: dict[int, list[int]] = {}
        for p, u in zip(pos, inverse, strict=True):
            members.setdefault(int(u), []).append(int(p))
        for group in members.values():
            if len(group) > 1:
                for other in group[1:]:
                    uf.union(group[0], other)
                    pair_list.append(np.array([[group[0], other, 0]]))
        for a, b, d in near_pairs_unique(uniq, threshold):
            ga, gb = members[int(a)], members[int(b)]
            uf.union(ga[0], gb[0])
            pair_list.append(np.array([[min(x, y), max(x, y), d] for x in ga for y in gb]))
    for group in exact_groups:
        for other in group[1:]:
            uf.union(int(group[0]), int(other))
            pair_list.append(np.array([[int(group[0]), int(other), 0]]))

    roots = np.array([uf.find(i) for i in range(n)])
    counts = np.bincount(roots, minlength=n)
    component = np.full(n, -1)
    multi = np.flatnonzero(counts[roots] > 1)
    _, comp_ids = np.unique(roots[multi], return_inverse=True)
    component[multi] = comp_ids
    pairs = (
        np.unique(np.concatenate(pair_list), axis=0) if pair_list
        else np.empty((0, 3), dtype=np.int64)
    )
    return DupResult(
        rows=df.index, exact_groups=exact_groups, near_pairs=pairs,
        component=component, n_components=int(comp_ids.max() + 1) if len(multi) else 0,
    )
