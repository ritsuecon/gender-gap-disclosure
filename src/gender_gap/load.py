"""CSV の読み込みと整形。

生 CSV は 236 列あり、同名列（雇用管理区分 1〜5 の繰り返し）を含む。
ここでは

* ``load_raw``       : 全列を文字列として読み込む
* ``build_companies``: 1 社 1 行の分析用テーブル（主要指標を短い英名に）
* ``build_kubun``    : 雇用管理区分ごとの項目を縦持ち（long）にしたテーブル

を提供する。
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .config import PROCESSED_DIR, SIZE_ORDER

# ---------------------------------------------------------------------------
# 列名マッピング（生 CSV 列名 -> 短い英名）
# pandas は重複列名に .1 .2 ... を付けるので、区分 1 の列は接尾辞なし。
# ---------------------------------------------------------------------------
COLUMN_MAP: dict[str, str] = {
    "企業名": "name",
    "法人番号": "corp_no",
    "女性活躍推進法に基づく一般事業主行動計画": "action_plan",
    "業種": "industry",
    "業種(詳細分類)": "industry_detail",
    "都道府県": "prefecture",
    "企業規模": "size",
    "市場区分": "market",
    "証券コード": "ticker",
    "企業認定等-くるみん認定": "kurumin",
    "企業認定等-プラチナくるみん認定": "platinum_kurumin",
    "企業認定等-えるぼし、または、えるぼしプラス認定": "eruboshi",
    "企業認定等-プラチナえるぼし、または、プラチナえるぼしプラス認定": "platinum_eruboshi",
    "企業認定等-令和7年度なでしこ銘柄": "nadeshiko",
    "企業認定等-ユースエール認定": "youth_yell",
    # 区分 1 の値（代表値として扱う）
    "1.採用した労働者に占める女性労働者の割合-雇用管理区分１": "hire_kubun1",
    "1.採用した労働者に占める女性労働者の割合-女性(%)": "female_hire_pct",
    "3.労働者に占める女性労働者の割合-雇用管理区分１": "worker_kubun1",
    "3.労働者に占める女性労働者の割合-女性(%)": "female_worker_pct",
    "4.(1)男女の平均継続勤務年数の差異-男性(年)": "tenure_male",
    "4.(1)男女の平均継続勤務年数の差異-女性(年)": "tenure_female",
    "5.男女別の育児休業取得率-雇用管理区分１": "leave_kubun1",
    "5.男女別の育児休業取得率-男性(%)": "parental_leave_male_pct",
    "5.男女別の育児休業取得率-女性(%)": "parental_leave_female_pct",
    "6.一月当たりの労働者の平均残業時間-公表する範囲": "overtime_scope",
    "6.一月当たりの労働者の平均残業時間-平均残業時間(時間)": "overtime_hours",
    "8.(1)年次有給休暇の取得率-対象労働者(%)": "paid_leave_pct",
    "9.係長級にある者に占める女性労働者の割合-割合(%)": "female_supervisor_pct",
    "10.管理職に占める女性労働者の割合-割合(%)": "female_manager_pct",
    "10.管理職に占める女性労働者の割合-人数(人)": "female_manager_n",
    "10.管理職に占める女性労働者の割合-男女計(人)": "manager_total",
    "11.役員に占める女性の割合-割合(%)": "female_officer_pct",
    "11.役員に占める女性の割合-人数(人)": "female_officer_n",
    "11.役員に占める女性の割合-男女計(人)": "officer_total",
    "13.男女別の再雇用-男性(人)": "rehire_male",
    "13.男女別の再雇用-女性(人)": "rehire_female",
    "13.中途採用の実績-男性(人)": "midcareer_male",
    "13.中途採用の実績-女性(人)": "midcareer_female",
    "14.男女の賃金の差異1-全労働者(%)": "pay_gap_all",
    "14.男女の賃金の差異2-うち正規雇用労働者(%)": "pay_gap_regular",
    "14.男女の賃金の差異3-うち非正規雇用労働者(%)": "pay_gap_nonregular",
    "14.男女の賃金の差異 注釈・説明": "pay_gap_note",
    "14.対象期間": "pay_gap_period",
    "15.データの対象-データの対象": "data_scope",
    "16.データ集計時点-データ集計時点": "data_asof",
    "職種・雇用形態転換制度": "sys_conversion",
    "正社員再雇用・中途採用制度": "sys_rehire",
    "教育訓練・研修制度": "sys_training",
    "キャリアコンサルティング制度": "sys_career",
    "フレックスタイム制度": "sys_flextime",
    "在宅勤務・テレワーク": "sys_telework",
    "短時間勤務制度": "sys_short_hours",
    "病気・不妊治療休暇": "sys_medical_leave",
    "年次有給休暇時間単位取得制度": "sys_hourly_leave",
    "データの最終更新日": "last_updated",
}

NUMERIC_COLS = [
    "female_hire_pct",
    "female_worker_pct",
    "tenure_male",
    "tenure_female",
    "parental_leave_male_pct",
    "parental_leave_female_pct",
    "overtime_hours",
    "paid_leave_pct",
    "female_supervisor_pct",
    "female_manager_pct",
    "female_manager_n",
    "manager_total",
    "female_officer_pct",
    "female_officer_n",
    "officer_total",
    "rehire_male",
    "rehire_female",
    "midcareer_male",
    "midcareer_female",
    "pay_gap_all",
    "pay_gap_regular",
    "pay_gap_nonregular",
]

SYSTEM_COLS = [c for c in COLUMN_MAP.values() if c.startswith("sys_")]

# 雇用管理区分 1〜5 を持つセクション: 接頭辞 -> {英名: 生列名の接尾辞}
KUBUN_SECTIONS: dict[str, dict[str, str]] = {
    "female_hire_pct": {"_prefix": "1.採用した労働者に占める女性労働者の割合", "value": "女性(%)"},
    "hire_ratio": {"_prefix": "2.採用における男女別の競争倍率", "male": "男性(倍)", "female": "女性(倍)"},
    "female_worker_pct": {"_prefix": "3.労働者に占める女性労働者の割合", "value": "女性(%)"},
    "tenure": {
        "_prefix": "4.(1)男女の平均継続勤務年数の差異",
        "male": "男性(年)",
        "female": "女性(年)",
        "diff": "差異(年)",
    },
    "retention10": {"_prefix": "4.(2)男女別の採用１０年前後の継続雇用割合", "male": "男性(%)", "female": "女性(%)"},
    "parental_leave": {"_prefix": "5.男女別の育児休業取得率", "male": "男性(%)", "female": "女性(%)"},
    "overtime": {"_prefix": "7.雇用管理区分ごとの一月当たりの労働者の平均残業時間", "value": "平均残業時間(時間)"},
    "paid_leave": {"_prefix": "8.(2)年次有給休暇の取得率(区)", "value": "有給休暇取得率(%)"},
    "headcount": {"_prefix": "12.男女別の職種", "male": "男性(人)", "female": "女性(人)"},
    "conversion": {"_prefix": "12.雇用形態の転換実績", "male": "男性(人)", "female": "女性(人)"},
}

_KUBUN_NUMS = ["１", "２", "３", "４", "５"]
_FULLWIDTH = str.maketrans("０１２３４５６７８９．，－", "0123456789.,-")


# ---------------------------------------------------------------------------
# 読み込み
# ---------------------------------------------------------------------------
def load_raw(csv_path: Path) -> pd.DataFrame:
    """全列を文字列で読み込む。BOM の有無はどちらでもよい。"""
    return pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, low_memory=False)


def to_number(s: pd.Series) -> pd.Series:
    """'1,234' '５０.０' '-' などを数値化する。変換できない値は NaN。"""
    cleaned = (
        s.astype("string")
        .str.strip()
        .str.translate(_FULLWIDTH)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("％", "", regex=False)
    )
    cleaned = cleaned.where(~cleaned.isin(["", "-", "ー", "―", "－", "非公表"]))
    return pd.to_numeric(cleaned, errors="coerce").astype("float64")


def _kubun_col(prefix: str, suffix: str, i: int) -> str:
    """区分 i (0 始まり) の列名。pandas の重複列名規則 (.1 .2 ...) に合わせる。"""
    base = f"{prefix}-{suffix}"
    return base if i == 0 else f"{base}.{i}"


def build_companies(raw: pd.DataFrame) -> pd.DataFrame:
    """1 社 1 行の分析用テーブルを作る。"""
    missing = [c for c in COLUMN_MAP if c not in raw.columns]
    if missing:
        raise KeyError(f"想定した列が CSV にありません: {missing[:5]} ...")

    df = raw[list(COLUMN_MAP)].rename(columns=COLUMN_MAP).copy()
    df.insert(0, "row_id", range(len(df)))

    for c in NUMERIC_COLS:
        df[c] = to_number(df[c])

    df["size"] = pd.Categorical(df["size"], categories=SIZE_ORDER, ordered=True)
    df["listed"] = df["market"].notna()
    df["prime"] = df["market"].eq("プライム（東証）")
    df["has_eruboshi"] = df["eruboshi"].fillna("").str.startswith("認定段階")
    df["has_platinum_eruboshi"] = df["platinum_eruboshi"].isin(["認定あり", "プラス認定あり"])
    df["has_kurumin"] = df["kurumin"].fillna("").str.startswith("認定あり")
    df["has_platinum_kurumin"] = df["platinum_kurumin"].fillna("").str.startswith("認定あり")
    df["has_nadeshiko"] = df["nadeshiko"].eq("認定あり")
    for c in SYSTEM_COLS:
        df[c] = df[c].notna()
    df["n_systems"] = df[SYSTEM_COLS].sum(axis=1)
    df["tenure_gap_years"] = df["tenure_male"] - df["tenure_female"]
    # 賃金差異がちょうど 100 の企業（バンチング分析用フラグ）
    for c in ["pay_gap_all", "pay_gap_regular", "pay_gap_nonregular"]:
        df[f"{c}_is100"] = df[c].eq(100.0)
    df["last_updated"] = pd.to_datetime(df["last_updated"], format="%Y年%m月%d日", errors="coerce")
    return df


def build_kubun(raw: pd.DataFrame) -> pd.DataFrame:
    """雇用管理区分ごとの項目を縦持ちにする。

    列: row_id, section, kubun_no (1-5), kubun, value/male/female/diff
    """
    frames: list[pd.DataFrame] = []
    for section, spec in KUBUN_SECTIONS.items():
        prefix = spec["_prefix"]
        for i, num in enumerate(_KUBUN_NUMS):
            name_col = f"{prefix}-雇用管理区分{num}"
            if name_col not in raw.columns:
                continue
            part = pd.DataFrame({"row_id": range(len(raw)), "kubun": raw[name_col]})
            for key, suffix in spec.items():
                if key == "_prefix":
                    continue
                col = _kubun_col(prefix, suffix, i)
                part[key] = to_number(raw[col]) if col in raw.columns else pd.NA
            part.insert(1, "section", section)
            part.insert(2, "kubun_no", i + 1)
            value_cols = [k for k in spec if k != "_prefix"]
            part = part[part["kubun"].notna() | part[value_cols].notna().any(axis=1)]
            frames.append(part)
    out = pd.concat(frames, ignore_index=True)
    for c in ["value", "male", "female", "diff"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def save_processed(companies: pd.DataFrame, kubun: pd.DataFrame, out_dir: Path = PROCESSED_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "companies_parquet": out_dir / "companies.parquet",
        "companies_csv": out_dir / "companies.csv",
        "kubun_parquet": out_dir / "kubun.parquet",
    }
    companies.to_parquet(paths["companies_parquet"], index=False)
    companies.to_csv(paths["companies_csv"], index=False, encoding="utf-8-sig")
    kubun.to_parquet(paths["kubun_parquet"], index=False)
    return paths


def load_processed(out_dir: Path = PROCESSED_DIR) -> tuple[pd.DataFrame, pd.DataFrame]:
    companies = pd.read_parquet(out_dir / "companies.parquet")
    companies["size"] = pd.Categorical(companies["size"], categories=SIZE_ORDER, ordered=True)
    kubun = pd.read_parquet(out_dir / "kubun.parquet")
    return companies, kubun


def source_date_from_filename(path: Path) -> str | None:
    """'99_20261016_utf8_bom.csv' -> '2026-10-16'"""
    m = re.search(r"_(\d{4})(\d{2})(\d{2})_", path.name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
