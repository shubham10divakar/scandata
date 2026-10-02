import io

import numpy as np
from PIL import Image

from scandata.extractors import extract
from scandata.extractors.decode import jpeg_quality
from scandata.extractors.file_meta import magic_format
from scandata.extractors.hashes import dhash, phash


def texture(seed=0, size=128):
    rng = np.random.default_rng(seed)
    small = rng.integers(0, 256, (8, 8, 3), dtype=np.uint8)
    return Image.fromarray(small).resize((size, size), Image.Resampling.BICUBIC)


def hamming(a, b):
    return bin(a ^ b).count("1")


def test_phash_robust_to_resize_and_recompress():
    a = texture(1)
    buf = io.BytesIO()
    a.resize((90, 90)).save(buf, format="JPEG", quality=60)
    b = Image.open(buf).convert("RGB")
    assert hamming(phash(a.convert("L")), phash(b.convert("L"))) <= 6
    assert hamming(dhash(a.convert("L")), dhash(b.convert("L"))) <= 10
    other = texture(2)
    assert hamming(phash(a.convert("L")), phash(other.convert("L"))) > 12


def test_jpeg_quality_estimate():
    for q in (50, 75, 95):
        buf = io.BytesIO()
        texture().save(buf, format="JPEG", quality=q)
        est = jpeg_quality(Image.open(io.BytesIO(buf.getvalue())))
        assert abs(est - q) <= 5, (q, est)


def test_magic_bytes():
    buf = io.BytesIO()
    texture().save(buf, format="PNG")
    assert magic_format(buf.getvalue()[:16]) == "PNG"
    assert magic_format(b"not an image") is None


def test_extract_good_and_bad_files(tmp_path):
    good = tmp_path / "g.jpg"
    texture().save(good, quality=90)
    rec = extract(str(good), target_size=32)
    assert rec["readable"] and rec["width"] == 128 and rec["mode"] == "RGB"
    assert 0 < rec["edge_density_target"] is not None
    assert len(rec["thumb"]) == 8 * 8 * 3 and len(rec["border"]) == 36 * 3

    zero = tmp_path / "z.jpg"
    zero.write_bytes(b"")
    assert extract(str(zero))["error"] == "zero-byte file"

    trunc = tmp_path / "t.jpg"
    trunc.write_bytes(good.read_bytes()[:200])
    bad = extract(str(trunc))
    assert not bad["readable"] and bad["error"]

    assert extract(str(tmp_path / "missing.jpg"))["error"] == "file not found"


def test_sixteen_bit_and_palette_images(tmp_path):
    arr = (np.arange(64 * 64).reshape(64, 64) * 16).astype(np.uint16)
    Image.fromarray(arr).save(tmp_path / "16.png")
    texture().convert("P").save(tmp_path / "p.png")
    for name in ("16.png", "p.png"):
        rec = extract(str(tmp_path / name))
        assert rec["readable"], rec["error"]
