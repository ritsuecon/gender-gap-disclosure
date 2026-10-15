import zipfile
from pathlib import Path

import pytest

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_utf8_bom.csv"


@pytest.fixture(scope="session")
def fixture_csv() -> Path:
    return FIXTURE_CSV


@pytest.fixture
def fixture_zip(tmp_path: Path) -> Path:
    z = tmp_path / "99_20260101_utf8_bom.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(FIXTURE_CSV, arcname="99_20260101_utf8_bom.csv")
    return z
