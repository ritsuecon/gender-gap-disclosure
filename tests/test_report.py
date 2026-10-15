import pandas as pd

from gender_gap import load as L
from gender_gap.report import build_report, md_table


def test_md_table_formats_ints_and_floats():
    df = pd.DataFrame({"n": [10.0, 2000.0], "中央値": [1.25, float("nan")]}, index=["a", "b"])
    out = md_table(df, "k")
    assert "| k | n | 中央値 |" in out
    assert "| a | 10 | 1.2 |" in out or "| a | 10 | 1.3 |" in out
    assert "| b | 2,000 |  |" in out


def test_build_report_end_to_end(fixture_csv, tmp_path):
    raw = L.load_raw(fixture_csv)
    c, k = L.build_companies(raw), L.build_kubun(raw)
    out = build_report(c, k, "2026-01-01", report_dir=tmp_path, fig_dir=tmp_path / "figures")
    text = out.read_text(encoding="utf-8")
    assert "2026-01-01時点" in text
    assert "## 4. 男女の賃金の差異" in text
    pngs = list((tmp_path / "figures").glob("*.png"))
    assert len(pngs) >= 9
