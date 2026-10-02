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


def test_dhash_must_confirm_phash_match():
    # rows 0/1 share a pHash but differ in 20 dHash bits (look-alikes, e.g. two leaves on one
    # background); rows 2/3 are a pHash-near pair that dHash confirms
    df = pd.DataFrame({
        "sha256": ["a", "b", "c", "d"],
        "phash": [0, 0, 2**64 - 1, 2**64 - 2],
        "dhash": [0, 2**20 - 1, 5, 7],
    })
    res = find_duplicates(df, threshold=6, dhash_threshold=10)
    assert {(int(a), int(b)) for a, b, _ in res.near_pairs} == {(2, 3)}
    assert res.component[0] == res.component[1] == -1
    assert res.n_components == 1


def test_dhash_keeps_byte_identical_files():
    df = pd.DataFrame({"sha256": ["a", "a"], "phash": [0, 2**64 - 1], "dhash": [0, 2**64 - 1]})
    res = find_duplicates(df, threshold=6, dhash_threshold=10)
    assert res.n_components == 1


def test_pixel_verifier_rejects_lookalikes(tmp_path):
    from PIL import Image

    from scandata.analysis.duplicates import pixel_verifier

    rng = np.random.default_rng(0)
    texture = rng.integers(0, 256, (128, 128), dtype=np.uint8)
    Image.fromarray(texture).save(tmp_path / "a.png")
    Image.fromarray(texture).resize((96, 96)).save(tmp_path / "a_small.jpg", quality=70)
    Image.fromarray(rng.integers(0, 256, (128, 128), dtype=np.uint8)).save(tmp_path / "b.png")
    paths = [str(tmp_path / n) for n in ("a.png", "a_small.jpg", "b.png")]
    keep = pixel_verifier(paths, 0.65)(np.array([[0, 1, 2], [0, 2, 2]]))
    assert keep.tolist() == [True, False]
