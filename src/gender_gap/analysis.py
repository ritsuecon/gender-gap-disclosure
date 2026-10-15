"""集計ロジック。すべて DataFrame を受け取り DataFrame を返す純粋関数。"""

from __future__ import annotations

import pandas as pd

from .config import PAY_GAP_MAX_PLAUSIBLE, SIZE_ORDER

# レポートで扱う主要指標: 英名 -> 日本語ラベル
INDICATORS: dict[str, str] = {
    "pay_gap_all": "男女の賃金の差異（全労働者, 男性=100）",
    "pay_gap_regular": "男女の賃金の差異（正規雇用, 男性=100）",
    "pay_gap_nonregular": "男女の賃金の差異（非正規雇用, 男性=100）",
    "female_manager_pct": "管理職に占める女性割合 (%)",
    "female_supervisor_pct": "係長級に占める女性割合 (%)",
    "female_officer_pct": "役員に占める女性割合 (%)",
    "female_worker_pct": "労働者に占める女性割合 (%) ※区分1",
    "female_hire_pct": "採用者に占める女性割合 (%) ※区分1",
    "parental_leave_male_pct": "男性の育児休業取得率 (%) ※区分1",
    "parental_leave_female_pct": "女性の育児休業取得率 (%) ※区分1",
    "tenure_gap_years": "平均継続勤務年数の男女差（男性−女性, 年）※区分1",
    "overtime_hours": "一月当たり平均残業時間 (時間)",
    "paid_leave_pct": "年次有給休暇取得率 (%)",
}

PAY_GAP_COLS = ["pay_gap_all", "pay_gap_regular", "pay_gap_nonregular"]


def plausible(df: pd.DataFrame) -> pd.DataFrame:
    """明らかな入力ミス（賃金差異 > 200% や育休取得率 > 100% など）を NaN にした複製を返す。"""
    out = df.copy()
    for c in PAY_GAP_COLS:
        out.loc[out[c] > PAY_GAP_MAX_PLAUSIBLE, c] = float("nan")
    for c in ["parental_leave_male_pct", "parental_leave_female_pct", "paid_leave_pct",
              "female_manager_pct", "female_supervisor_pct", "female_officer_pct",
              "female_worker_pct", "female_hire_pct"]:
        out.loc[(out[c] > 100) | (out[c] < 0), c] = float("nan")
    out.loc[out["overtime_hours"] < 0, "overtime_hours"] = float("nan")
    return out


def implausible_counts(df: pd.DataFrame) -> pd.DataFrame:
    """plausible() で除外される件数を指標ごとに数える。"""
    rows = []
    for c in PAY_GAP_COLS:
        rows.append({"指標": INDICATORS[c], "除外件数": int((df[c] > PAY_GAP_MAX_PLAUSIBLE).sum()),
                     "条件": f"> {PAY_GAP_MAX_PLAUSIBLE:.0f}%"})
    for c in ["parental_leave_male_pct", "parental_leave_female_pct", "paid_leave_pct"]:
        rows.append({"指標": INDICATORS[c], "除外件数": int(((df[c] > 100) | (df[c] < 0)).sum()), "条件": "<0 or >100"})
    rows.append({"指標": INDICATORS["overtime_hours"], "除外件数": int((df["overtime_hours"] < 0).sum()), "条件": "<0"})
    return pd.DataFrame(rows)


def overview(df: pd.DataFrame) -> dict[str, int]:
    return {
        "企業数": len(df),
        "法人番号あり": int(df["corp_no"].notna().sum()),
        "上場企業（市場区分あり）": int(df["listed"].sum()),
        "東証プライム": int(df["prime"].sum()),
        "えるぼし認定": int(df["has_eruboshi"].sum()),
        "プラチナえるぼし認定": int(df["has_platinum_eruboshi"].sum()),
        "くるみん認定": int(df["has_kurumin"].sum()),
        "プラチナくるみん認定": int(df["has_platinum_kurumin"].sum()),
        "なでしこ銘柄": int(df["has_nadeshiko"].sum()),
    }


def disclosure_rates(df: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """各指標を公表している企業の割合 (%)。by を指定するとその列ごと。"""
    cols = list(INDICATORS)
    if by is None:
        rate = df[cols].notna().mean().mul(100).round(1)
        out = pd.DataFrame({"公表率(%)": rate, "公表社数": df[cols].notna().sum()})
        out.index = [INDICATORS[c] for c in out.index]
        return out
    g = df.groupby(by, observed=True)[cols].apply(lambda x: x.notna().mean().mul(100).round(1))
    g.columns = [INDICATORS[c] for c in g.columns]
    g.insert(0, "企業数", df.groupby(by, observed=True).size())
    return g


def summarize(df: pd.DataFrame, metric: str, by: str, min_n: int = 30) -> pd.DataFrame:
    """metric を by ごとに件数・中央値・平均・四分位で要約する。件数 < min_n は除く。"""
    g = df.groupby(by, observed=True)[metric]
    out = pd.DataFrame({
        "n": g.count(),
        "中央値": g.median(),
        "平均": g.mean(),
        "Q1": g.quantile(0.25),
        "Q3": g.quantile(0.75),
    })
    out = out[out["n"] >= min_n].round(1)
    if by == "size":
        out = out.reindex([s for s in SIZE_ORDER if s in out.index])
    else:
        out = out.sort_values("中央値")
    return out


def overall_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for c, label in INDICATORS.items():
        s = df[c].dropna()
        rows[label] = {"n": len(s), "中央値": s.median(), "平均": s.mean(), "Q1": s.quantile(0.25),
                       "Q3": s.quantile(0.75), "最小": s.min(), "最大": s.max()}
    return pd.DataFrame(rows).T.round(1)


def pay_gap_bands(df: pd.DataFrame, col: str = "pay_gap_all") -> pd.DataFrame:
    """賃金差異の分布を帯で集計する。"""
    bins = [0, 50, 60, 70, 80, 90, 100, 200]
    labels = ["〜50", "50〜60", "60〜70", "70〜80", "80〜90", "90〜100", "100超（女性が高い）"]
    s = pd.cut(df[col].dropna(), bins=bins, labels=labels, right=False)
    counts = s.value_counts(sort=False)
    return pd.DataFrame({"社数": counts, "構成比(%)": (counts / counts.sum() * 100).round(1)})


def certification_effect(df: pd.DataFrame, flag: str, metric: str) -> pd.DataFrame:
    """認定あり/なしで metric の中央値を企業規模別に比較する（規模の交絡をおおまかに除く）。"""
    g = df.groupby(["size", flag], observed=True)[metric].agg(["count", "median"]).unstack(flag)
    g.columns = [f"{'認定あり' if flag_ else '認定なし'}_{stat}" for stat, flag_ in g.columns]
    g = g.rename(columns={"認定あり_count": "認定あり n", "認定なし_count": "認定なし n",
                          "認定あり_median": "認定あり 中央値", "認定なし_median": "認定なし 中央値"})
    g["差（あり−なし）"] = g["認定あり 中央値"] - g["認定なし 中央値"]
    return g.round(1)


def listed_comparison(df: pd.DataFrame, metrics: list[str] | None = None) -> pd.DataFrame:
    metrics = metrics or ["pay_gap_all", "pay_gap_regular", "female_manager_pct", "female_officer_pct",
                          "parental_leave_male_pct", "overtime_hours", "paid_leave_pct"]
    group = pd.Series("非上場", index=df.index)
    group[df["listed"]] = "上場（プライム以外）"
    group[df["prime"]] = "東証プライム"
    out = df.groupby(group)[metrics].median().round(1)
    out.columns = [INDICATORS[m] for m in metrics]
    out.insert(0, "企業数", group.value_counts())
    return out.reindex(["東証プライム", "上場（プライム以外）", "非上場"])


def correlations(df: pd.DataFrame, metrics: list[str] | None = None) -> pd.DataFrame:
    metrics = metrics or ["pay_gap_all", "pay_gap_regular", "female_manager_pct", "female_worker_pct",
                          "female_officer_pct", "parental_leave_male_pct", "tenure_gap_years",
                          "overtime_hours", "paid_leave_pct"]
    c = df[metrics].corr(method="spearman").round(2)
    c.index = c.columns = [INDICATORS[m].split(" ")[0].split("（")[0] for m in metrics]
    return c


def system_adoption(df: pd.DataFrame) -> pd.DataFrame:
    """両立支援制度の導入率を企業規模別に出す。"""
    labels = {
        "sys_conversion": "職種・雇用形態転換", "sys_rehire": "正社員再雇用・中途採用", "sys_training": "教育訓練・研修",
        "sys_career": "キャリアコンサルティング", "sys_flextime": "フレックスタイム", "sys_telework": "在宅勤務・テレワーク",
        "sys_short_hours": "短時間勤務", "sys_medical_leave": "病気・不妊治療休暇", "sys_hourly_leave": "有給の時間単位取得",
    }
    g = df.groupby("size", observed=True)[list(labels)].mean().mul(100).round(1)
    g.columns = [labels[c] for c in g.columns]
    g.insert(0, "企業数", df.groupby("size", observed=True).size())
    return g


def top_bottom(summary: pd.DataFrame, n: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """summarize() の結果から中央値の上位/下位を取り出す。"""
    s = summary.sort_values("中央値")
    return s.head(n), s.tail(n).iloc[::-1]
