from pathlib import Path

import pytest

from gender_gap import extract as X
from gender_gap.download import resolve_code


def test_extract_zip(fixture_zip: Path, tmp_path: Path):
    out = tmp_path / "out"
    paths = X.extract(fixture_zip, out_dir=out)
    assert len(paths) == 1
    assert paths[0].name == "99_20260101_utf8_bom.csv"
    assert paths[0].stat().st_size > 0
    assert X.find_latest_csv(out) == paths[0]


def test_find_latest_zip_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        X.find_latest_zip(tmp_path)


def test_resolve_code():
    assert resolve_code("全体版") == 99
    assert resolve_code("建設業") == 4
    assert resolve_code("57") == 57
    assert resolve_code(51) == 51
    with pytest.raises(ValueError):
        resolve_code("存在しない業種")
