import pandas as pd

from gender_gap import load as L


def test_to_number_handles_japanese_formats():
    s = pd.Series(["1,234", "５０.０", "-", "", "80%", None, "abc", "－"])
    out = L.to_number(s)
    assert out.tolist()[:2] == [1234.0, 50.0]
    assert out[4] == 80.0
    assert out[[2, 3, 5, 6, 7]].isna().all()
    assert str(out.dtype) == "float64"


def test_build_companies(fixture_csv):
    raw = L.load_raw(fixture_csv)
    df = L.build_companies(raw)
    assert len(df) == 60
    assert df["size"].cat.ordered
    assert list(df["size"].cat.categories) == L.SIZE_ORDER
    assert df["pay_gap_all"].dtype == "float64"
    # "1,200" がカンマ除去されて数値化される
    assert df.loc[1, "manager_total"] == 1200
    # 制度列は bool
    assert df["sys_telework"].dtype == bool
    assert df["sys_short_hours"].all()
    assert df["has_eruboshi"].sum() == 15
    assert df["has_kurumin"].sum() == 12
    assert df["prime"].sum() == 6
    assert pd.api.types.is_datetime64_any_dtype(df["last_updated"])


def test_build_kubun_uses_pandas_duplicate_suffix(fixture_csv):
    raw = L.load_raw(fixture_csv)
    k = L.build_kubun(raw)
    pl = k[k["section"] == "parental_leave"]
    # 区分1 は全社、区分2 は偶数行のみ
    assert (pl["kubun_no"] == 1).sum() == 60
    assert (pl["kubun_no"] == 2).sum() == 30
    k2 = pl[pl["kubun_no"] == 2]
    assert (k2["kubun"] == "パート").all()
    assert (k2["male"] == 25).all()


def test_source_date_from_filename(tmp_path):
    assert L.source_date_from_filename(tmp_path / "99_20261016_utf8_bom.csv") == "2026-10-16"
    assert L.source_date_from_filename(tmp_path / "foo.csv") is None


def test_save_and_load_roundtrip(fixture_csv, tmp_path):
    raw = L.load_raw(fixture_csv)
    c, k = L.build_companies(raw), L.build_kubun(raw)
    L.save_processed(c, k, out_dir=tmp_path)
    c2, k2 = L.load_processed(tmp_path)
    assert len(c2) == len(c) and len(k2) == len(k)
    assert c2["size"].cat.ordered
