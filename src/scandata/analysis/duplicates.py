"""Exact and near-duplicate detection.

Near duplicates use multi-index hashing: with a Hamming threshold t, two 64-bit hashes
within distance t must agree exactly on at least one of t+1 disjoint bit chunks
(pigeonhole). So we bucket by each chunk and only compare hashes that share a bucket,
with vectorised popcounts. Identical hashes are collapsed first so clusters of exact
copies don't explode into n^2 pairs.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from PIL import Image

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


def find_duplicates(
    df: pd.DataFrame, threshold: int, exclude: pd.Series | None = None,
    dhash_threshold: int | None = None,
    verify: Callable[[np.ndarray], np.ndarray] | None = None,
) -> DupResult:
    """`df` holds readable rows with sha256 and phash. `exclude` marks rows skipped for near-dups
    (e.g. blank images, which all share one hash).

    pHash only sees low frequencies, so different objects framed alike on a plain background
    (PlantVillage leaves) can land within the threshold. With `dhash_threshold`, a pHash match
    must also be within that many dHash bits (needs a `dhash` column). Both hashes are 64 bits,
    so on large datasets look-alikes still slip through; `verify` (see `pixel_verifier`) gets
    the surviving (k, 3) candidate pairs and returns a keep mask. Byte-identical files are
    always kept."""
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
        members: dict[int, list[int]] = {}
        for p, u in zip(pos, inverse, strict=True):
            members.setdefault(int(u), []).append(int(p))
        candidates: list[np.ndarray] = []
        for group in members.values():
            if len(group) > 1:  # identical pHash: distance 0
                g = np.asarray(group)
                # chain, so big groups don't explode into n^2 pairs (unless each pair is checked)
                if dhash_threshold is None and verify is None:
                    candidates.append(np.stack([np.full(len(g) - 1, g[0]), g[1:],
                                                np.zeros(len(g) - 1, dtype=np.int64)], axis=1))
                else:
                    i, j = np.triu_indices(len(g), k=1)
                    candidates.append(np.stack([g[i], g[j], np.zeros(len(i), dtype=np.int64)],
                                               axis=1))
        for a, b, d in near_pairs_unique(uniq, threshold):
            ga, gb = members[int(a)], members[int(b)]
            candidates.append(np.array([[min(x, y), max(x, y), d] for x in ga for y in gb]))
        if candidates:
            cand = np.concatenate(candidates).astype(np.int64)
            if dhash_threshold is not None:
                dh = np.array([int(h) for h in df["dhash"].to_numpy()], dtype=np.uint64)
                cand = cand[np.bitwise_count(dh[cand[:, 0]] ^ dh[cand[:, 1]]) <= dhash_threshold]
            if verify is not None and len(cand):
                identical = sha[cand[:, 0]] == sha[cand[:, 1]]
                cand = cand[identical | np.asarray(verify(cand), dtype=bool)]
            for a, b, _ in cand:
                uf.union(int(a), int(b))
            pair_list.append(cand)
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


def _edge_map(path: str, size: int) -> np.ndarray | None:
    try:
        with Image.open(path) as im:
            g = np.asarray(im.convert("L").resize((size, size), Image.Resampling.BILINEAR),
                           dtype=np.float64)
    except Exception:  # noqa: BLE001 - unreadable now; caller keeps the hash evidence
        return None
    gy, gx = np.gradient(g)
    e = np.hypot(gx, gy)
    e -= e.mean()
    return e / (np.linalg.norm(e) + 1e-9)


def pixel_verifier(
    paths: Sequence[str], min_corr: float, size: int = 64
) -> Callable[[np.ndarray], np.ndarray]:
    """Confirm hash matches on pixels: correlation of gradient magnitudes on a size x size
    grayscale thumbnail. Copies (resized, recompressed, lightly cropped) keep their edges and
    texture; different objects with a similar silhouette on a shared background do not.
    On PlantVillage, look-alike leaves scored <= 0.59 and re-saved copies >= 0.67."""

    def verify(pairs: np.ndarray) -> np.ndarray:
        cache: dict[int, np.ndarray | None] = {}

        def edges(i: int) -> np.ndarray | None:
            if i not in cache:
                cache[i] = _edge_map(paths[i], size)
            return cache[i]

        keep = np.ones(len(pairs), dtype=bool)
        for k, (a, b, _) in enumerate(pairs):
            ea, eb = edges(int(a)), edges(int(b))
            if ea is not None and eb is not None:
                keep[k] = float((ea * eb).sum()) >= min_corr
        return keep

    return verify
