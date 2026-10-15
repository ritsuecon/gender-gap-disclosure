import pandas as pd
import pytest

from gender_gap import analysis as A
from gender_gap import load as L


@pytest.fixture(scope="module")
def companies(fixture_csv):
    return L.build_companies(L.load_raw(fixture_csv))


def test_plausible_drops_outliers(companies):
    assert companies.loc[1, "pay_gap_all"] > 200
    assert companies.loc[2, "parental_leave_male_pct"] == 500
    df = A.plausible(companies)
    assert pd.isna(df.loc[1, "pay_gap_all"])
    assert pd.isna(df.loc[2, "parental_leave_male_pct"])
    counts = A.implausible_counts(companies).set_index("指標")["除外件数"]
    assert counts[A.INDICATORS["pay_gap_all"]] == 1
    assert counts[A.INDICATORS["parental_leave_male_pct"]] == 1


def test_disclosure_rates(companies):
    r = A.disclosure_rates(companies)
    assert set(r.columns) == {"公表率(%)", "公表社数"}
    assert r.loc[A.INDICATORS["pay_gap_all"], "公表社数"] == 49
    by_size = A.disclosure_rates(companies, "size")
    assert list(by_size.index) == L.SIZE_ORDER
    assert by_size["企業数"].sum() == 60


def test_summarize_respects_min_n_and_order(companies):
    s = A.summarize(companies, "pay_gap_all", "size", min_n=1)
    assert list(s.index) == L.SIZE_ORDER
    assert set(s.columns) == {"n", "中央値", "平均", "Q1", "Q3"}
    assert A.summarize(companies, "pay_gap_all", "size", min_n=1000).empty


def test_pay_gap_bands_sum_to_100(companies):
    b = A.pay_gap_bands(A.plausible(companies))
    assert abs(b["構成比(%)"].sum() - 100) < 0.5


def test_certification_and_listed(companies):
    df = A.plausible(companies)
    ce = A.certification_effect(df, "has_eruboshi", "pay_gap_all")
    assert "差（あり−なし）" in ce.columns
    lc = A.listed_comparison(df)
    assert list(lc.index) == ["東証プライム", "上場（プライム以外）", "非上場"]
    assert lc.loc["東証プライム", "企業数"] == 6


def test_correlations_and_systems(companies):
    c = A.correlations(companies)
    assert c.shape[0] == c.shape[1]
    s = A.system_adoption(companies)
    assert s["短時間勤務"].eq(100).all()
