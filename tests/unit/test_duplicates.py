import numpy as np
import pandas as pd

from scandata.analysis.duplicates import find_duplicates, near_pairs_unique


def brute_force(hashes, t):
    out = set()
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            d = bin(int(hashes[i]) ^ int(hashes[j])).count("1")
            if d <= t:
                out.add((i, j, d))
    return out


def test_multi_index_matches_brute_force():
    rng = np.random.default_rng(0)
    base = rng.integers(0, 2**63, 300, dtype=np.int64).astype(np.uint64)
    # plant neighbours at distance 1..8
    planted = []
    for k, h in enumerate(base[:40]):
        flips = rng.choice(64, size=1 + k % 8, replace=False)
        v = int(h)
        for f in flips:
            v ^= 1 << int(f)
        planted.append(v)
    hashes = np.unique(np.concatenate([base, np.array(planted, dtype=np.uint64)]))
    for t in (4, 6, 8):
        got = {tuple(int(x) for x in row) for row in near_pairs_unique(hashes, t)}
        assert got == brute_force(hashes, t)


def test_find_duplicates_groups_and_components():
    df = pd.DataFrame({
        "sha256": ["a", "a", "b", "c", "d"],
        "phash": [0, 0, 0b111, 2**64 - 1, 2**64 - 2],
    })
    res = find_duplicates(df, threshold=6)
    assert [list(g) for g in res.exact_groups] == [[0, 1]]
    # 0,1 identical; 2 is within 3 bits of them; 3 and 4 are one bit apart
    assert res.component[0] == res.component[1] == res.component[2] != -1
    assert res.component[3] == res.component[4] != res.component[0]
    assert res.n_components == 2


def test_excluded_rows_skip_near_dup_search():
    df = pd.DataFrame({"sha256": ["a", "b", "c"], "phash": [5, 5, 5]})
    res = find_duplicates(df, threshold=6, exclude=pd.Series([True, True, False]))
    assert res.n_components == 0
