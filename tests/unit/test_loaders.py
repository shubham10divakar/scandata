import pandas as pd
import pytest
from PIL import Image

from scandata.loaders import LoaderError, load


def img(path, size=(16, 16)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (10, 20, 30)).save(path)


def test_class_folders_with_nested_domains(tmp_path):
    img(tmp_path / "D" / "CD" / "a.jpg")
    img(tmp_path / "D" / "UD" / "b.jpg")
    img(tmp_path / "W" / "CW" / "c.jpg")
    (tmp_path / "W" / "CW" / "Thumbs.db").write_bytes(b"x")
    (tmp_path / "W" / "empty").mkdir()
    index = load(tmp_path)
    assert index.layout == "class-folders"
    assert sorted(index.labels) == ["CD", "CW", "UD"]
    assert set(index.df["domain"]) == {"D", "W"}
    assert index.class_counts["empty"] == 0
    assert ("W/CW/Thumbs.db", "not an image file") in index.stray
    assert not index.has_splits


def test_split_folders_and_aliases(tmp_path):
    for split in ("train", "valid", "Test"):
        img(tmp_path / split / "cat" / "1.png")
        img(tmp_path / split / "dog" / "2.png")
    (tmp_path / "README.txt").write_text("hi")
    index = load(tmp_path)
    assert index.layout == "split-folders"
    assert index.splits == ["train", "val", "test"]
    assert index.held_out == ["val", "test"]
    assert ("README.txt", "outside the split folders") in index.stray


def test_splits_none_ignores_split_folders(tmp_path):
    img(tmp_path / "train" / "cat" / "1.png")
    img(tmp_path / "test" / "dog" / "2.png")
    index = load(tmp_path, splits="none")
    assert index.df["split"].isna().all()
    assert set(index.df["domain"]) == {"train", "test"}


def test_manifest_layout_and_group_regex(tmp_path):
    img(tmp_path / "images" / "p01_a.png")
    img(tmp_path / "images" / "p02_b.png")
    pd.DataFrame({
        "path": ["images/p01_a.png", "images/p02_b.png", "images/missing.png"],
        "label": ["x", "y", "x"], "split": ["train", "validation", "test"],
    }).to_csv(tmp_path / "labels.csv", index=False)
    index = load(tmp_path, group_regex=r"^(?P<group>p\d+)_")
    assert index.layout == "manifest"
    assert index.splits == ["train", "val", "test"]
    assert index.df["group"].tolist()[:2] == ["p01", "p02"]
    assert index.groups_declared


def test_errors(tmp_path):
    with pytest.raises(LoaderError, match="No images"):
        load(tmp_path)
    img(tmp_path / "a" / "1.png")
    with pytest.raises(LoaderError, match="named group"):
        load(tmp_path, group_regex=r"^(\d+)_")
