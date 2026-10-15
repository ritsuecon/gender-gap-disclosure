import pandas as pd
import pytest

from gender_gap import bunching as B
from gender_gap import load as L
from gender_gap.report import build_bunching_report


@pytest.fixture(scope="module")
def companies(fixture_csv):
    return L.build_companies(L.load_raw(fixture_csv))


def test_is100_flag(companies):
    assert companies["pay_gap_all_is100"].sum() == 7
    assert companies["pay_gap_regular_is100"].sum() == 2


def test_fine_histogram_bins(companies):
    h = B.fine_histogram(companies, "pay_gap_all", lo=95, hi=105, width=1.0)
    assert len(h) == 10
    assert h.loc[h["bin_left"] == 100, "count"].item() == 7
    assert h.loc[h["bin_left"] == 99, "count"].item() == 1
    assert h.loc[h["bin_left"] == 101, "count"].item() == 1


def test_excess_mass(companies):
    em = B.excess_mass(companies, "pay_gap_all", points=[100], bandwidth=2.5)
    assert em.loc[100, "ちょうどその値の社数"] == 7
    # 近傍は 99 と 101 の 2 社 → 密度 0.4/pt → 超過倍率 17.5
    assert em.loc[100, "近傍の密度（社/1pt）"] == 0.4
    assert em.loc[100, "超過倍率"] == 17.5


def test_window_and_consistency(companies):
    w = B.window_counts(companies)
    assert w.loc["ちょうど 100.0", "社数"] == 7
    c = B.consistency(companies)["社数"]
    assert c["全労働者がちょうど100の企業"] == 7
    assert c["　うち正規雇用も100"] == 2


def test_note_classification_and_examples(companies):
    assert B.classify_note("男女の賃金の差異はありません。") == "賃金制度に男女差がない旨の説明"
    assert B.classify_note("平均年間賃金を算出") == "計算方法・算出根拠の説明"
    assert B.classify_note(None) == "注釈なし"
    assert B.classify_note("特になし") == "その他"
    nc = B.note_classification(companies)
    assert nc.loc["賃金制度に男女差がない旨の説明", "ちょうど100"] == 3
    assert "男女の賃金の差異はありません。" in B.note_examples(companies)


def test_note_mentions_other_value():
    df = pd.DataFrame({"pay_gap_all": [100.0, 100.0, 80.0], "pay_gap_note": ["実際は115%です", "100%です", "70%"]})
    assert B.note_mentions_other_value(df) == 1


def test_impact_and_shares(companies):
    imp = B.impact_on_stats(companies)
    assert imp.loc["全労働者", "n（含む）"] - imp.loc["全労働者", "n（除外）"] == 7
    s = B.share_by(companies, "size", min_n=1)
    assert list(s.index) == L.SIZE_ORDER
    assert s["ちょうど100の社数"].sum() == 7
    assert set(B.share_listed(companies).index) <= {"上場", "非上場"}


def test_build_bunching_report(companies, tmp_path):
    out = build_bunching_report(companies, "2026-01-01", report_dir=tmp_path, fig_dir=tmp_path / "figures")
    text = out.read_text(encoding="utf-8")
    assert "ちょうど 100" in text
    assert "## 6. 解釈と推奨" in text
    assert len(list((tmp_path / "figures").glob("bunch_*.png"))) == 5
