"""男女の賃金の差異が「ちょうど 100」に集中する（バンチング）現象の分析。

男性賃金を 100 とした女性賃金の比は、実際の平均値から計算すれば小数になり、
正確に 100.0 になることは稀なはず。しかし公表値には 100.0 がスパイク状に集中している。
ここでは

* スパイクの大きさ（近傍の密度と比べた超過倍率）
* 他のキリ番（50, 60, 70, ...）との比較
* 100 と答えた企業の属性・整合性（正規／非正規も 100 か、単一性別か）
* 注釈欄の文言
* 全体統計への影響

を集計する。
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .config import SIZE_ORDER

PAY_GAP_COLS = {
    "pay_gap_all": "全労働者",
    "pay_gap_regular": "正規雇用",
    "pay_gap_nonregular": "非正規雇用",
}

ROUND_POINTS = [50, 60, 70, 75, 80, 90, 100, 110, 120]

# 注釈欄の分類に使う正規表現
NOTE_PATTERNS: dict[str, str] = {
    "賃金制度に男女差がない旨の説明": r"差異?(は|が)?(なし|無し|ない|無い|ありません|生じ|発生し)|同一(賃金|の賃金|労働|基準|体系|額)|同額|同率|同じ|差をつけ|差を設け|性別(に|で|による|を理由)|男女(で|による|問わず|関係なく|の区別|によって|を理由)|関係なく|区別なく|差別",
    "計算方法・算出根拠の説明": r"算出|計算|÷|／|×\s*100|平均(年間)?賃金|総支給|基本給|手当|年収",
    "人員構成・勤続年数などによる説明": r"勤続|年齢|役職|管理職|人員構成|構成比|年功|等級|職種|パート|短時間|時短|非正規",
}


# ---------------------------------------------------------------------------
# 分布の形
# ---------------------------------------------------------------------------
def fine_histogram(df: pd.DataFrame, col: str = "pay_gap_all", lo: float = 70, hi: float = 130,
                   width: float = 0.5) -> pd.DataFrame:
    """[lo, hi) を width 刻みで数える。bin_left が左端。"""
    s = df[col].dropna()
    edges = np.arange(lo, hi + width, width)
    counts, _ = np.histogram(s, bins=edges)
    return pd.DataFrame({"bin_left": edges[:-1], "count": counts})


def excess_mass(df: pd.DataFrame, col: str = "pay_gap_all", points: list[float] = ROUND_POINTS,
                bandwidth: float = 2.5) -> pd.DataFrame:
    """各点 v について、ちょうど v の社数と、±bandwidth（v 自身を除く）の 1 ポイント当たり密度を比べる。

    超過倍率 = ちょうど v の社数 / 近傍密度。実測値が滑らかに分布していれば
    ちょうど v になる確率は小数 1 桁刻みで 1/10 程度なので、倍率 1 を大きく超えればバンチング。
    """
    s = df[col].dropna()
    rows = []
    for v in points:
        exact = int((s == v).sum())
        nb = s[(s > v - bandwidth) & (s < v + bandwidth) & (s != v)]
        density = len(nb) / (2 * bandwidth)
        rows.append({
            "値": v,
            "ちょうどその値の社数": exact,
            "近傍の密度（社/1pt）": round(density, 1),
            "超過倍率": round(exact / density, 1) if density > 0 else np.nan,
            "全公表社に占める割合(%)": round(exact / len(s) * 100, 2),
        })
    return pd.DataFrame(rows).set_index("値")


def window_counts(df: pd.DataFrame, col: str = "pay_gap_all") -> pd.DataFrame:
    """100 の周辺を帯で数える。"""
    s = df[col].dropna()
    bands = [
        ("95.0〜97.4", (s >= 95) & (s < 97.5)),
        ("97.5〜99.9", (s >= 97.5) & (s < 100)),
        ("ちょうど 100.0", s == 100),
        ("100.1〜102.5", (s > 100) & (s <= 102.5)),
        ("102.6〜105.0", (s > 102.5) & (s <= 105)),
    ]
    return pd.DataFrame({"社数": [int(m.sum()) for _, m in bands]}, index=[b for b, _ in bands])


def rounding_shares(df: pd.DataFrame) -> pd.DataFrame:
    """丸め（整数、5 の倍数、10 の倍数、100）の割合を雇用形態別に。"""
    rows = {}
    for col, label in PAY_GAP_COLS.items():
        s = df[col].dropna()
        rows[label] = {
            "n": len(s),
            "整数値の割合(%)": round((s % 1 == 0).mean() * 100, 1),
            "5の倍数の割合(%)": round((s % 5 == 0).mean() * 100, 1),
            "10の倍数の割合(%)": round((s % 10 == 0).mean() * 100, 1),
            "ちょうど100の割合(%)": round((s == 100).mean() * 100, 2),
            "100超の割合(%)": round((s > 100).mean() * 100, 1),
        }
    return pd.DataFrame(rows).T


# ---------------------------------------------------------------------------
# 誰が 100 と答えているか
# ---------------------------------------------------------------------------
def share_by(df: pd.DataFrame, by: str, col: str = "pay_gap_all", min_n: int = 100) -> pd.DataFrame:
    d = df[df[col].notna()]
    g = d.groupby(by, observed=True)[col]
    out = pd.DataFrame({"公表社数": g.size(), "ちょうど100の社数": g.apply(lambda x: int((x == 100).sum()))})
    out["割合(%)"] = (out["ちょうど100の社数"] / out["公表社数"] * 100).round(2)
    out = out[out["公表社数"] >= min_n]
    if by == "size":
        return out.reindex([s for s in SIZE_ORDER if s in out.index])
    return out.sort_values("割合(%)", ascending=False)


def share_listed(df: pd.DataFrame, col: str = "pay_gap_all") -> pd.DataFrame:
    group = pd.Series("非上場", index=df.index)
    group[df["listed"]] = "上場"
    return share_by(df.assign(_g=group), "_g", col, min_n=1).rename_axis("区分")


def consistency(df: pd.DataFrame) -> pd.DataFrame:
    """全労働者=100 の企業で、正規・非正規も 100 か。"""
    e = df[df["pay_gap_all"] == 100]
    reg, non = e["pay_gap_regular"], e["pay_gap_nonregular"]
    rows = {
        "全労働者がちょうど100の企業": len(e),
        "　うち正規雇用も100": int((reg == 100).sum()),
        "　うち非正規雇用も100": int((non == 100).sum()),
        "　うち正規・非正規ともに100": int(((reg == 100) & (non == 100)).sum()),
        "　うち正規雇用が未記入": int(reg.isna().sum()),
        "　うち正規雇用が100以外の値": int(((reg != 100) & reg.notna()).sum()),
    }
    return pd.DataFrame({"社数": rows})


def single_sex_profile(df: pd.DataFrame) -> pd.DataFrame:
    """100 と答えた企業と、それ以外の公表企業で、女性労働者割合（区分1）の分布を比べる。

    女性または男性が 0 人なら比率は定義できないため、100 を置いている可能性を見る。
    """
    d = df[df["pay_gap_all"].notna()].copy()
    d["grp"] = np.where(d["pay_gap_all"] == 100, "ちょうど100", "それ以外")
    bins = [-0.1, 0, 10, 90, 99.9, 100]
    labels = ["0%（女性0人）", "0超〜10%", "10〜90%", "90超〜100%未満", "100%（男性0人）"]
    d["band"] = pd.cut(d["female_worker_pct"], bins=bins, labels=labels)
    d["band"] = d["band"].cat.add_categories(["未記入"]).fillna("未記入")
    ct = pd.crosstab(d["band"], d["grp"])
    pct = (ct / ct.sum() * 100).round(1)
    pct.columns = [f"{c} (%)" for c in pct.columns]
    return pd.concat([ct, pct], axis=1)


def manager_profile(df: pd.DataFrame) -> pd.DataFrame:
    """100 と答えた企業と、それ以外で、女性管理職割合が 0% / 100% の割合など。"""
    d = df[df["pay_gap_all"].notna()].copy()
    d["grp"] = np.where(d["pay_gap_all"] == 100, "ちょうど100", "それ以外")
    g = d.groupby("grp")
    out = pd.DataFrame({
        "n": g.size(),
        "女性管理職割合を公表(%)": g["female_manager_pct"].apply(lambda x: x.notna().mean() * 100),
        "　うち0%(%)": g["female_manager_pct"].apply(lambda x: (x == 0).sum() / max(x.notna().sum(), 1) * 100),
        "　うち100%(%)": g["female_manager_pct"].apply(lambda x: (x == 100).sum() / max(x.notna().sum(), 1) * 100),
        "管理職の人数 中央値": g["manager_total"].median(),
        "女性労働者割合 中央値": g["female_worker_pct"].median(),
        "注釈記入率(%)": g["pay_gap_note"].apply(lambda x: x.notna().mean() * 100),
    }).round(1)
    return out.reindex(["ちょうど100", "それ以外"])


# ---------------------------------------------------------------------------
# 注釈欄
# ---------------------------------------------------------------------------
def classify_note(text) -> str:
    if text is None or (isinstance(text, float) and np.isnan(text)) or text is pd.NA:
        return "注釈なし"
    t = str(text)
    for label, pat in NOTE_PATTERNS.items():
        if re.search(pat, t):
            return label
    return "その他"


def note_classification(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["pay_gap_all"].notna()].copy()
    d["grp"] = np.where(d["pay_gap_all"] == 100, "ちょうど100", "それ以外")
    d["cls"] = d["pay_gap_note"].map(classify_note)
    order = ["注釈なし", *NOTE_PATTERNS, "その他"]
    ct = pd.crosstab(d["cls"], d["grp"]).reindex(order).fillna(0).astype(int)
    pct = (ct / ct.sum() * 100).round(1)
    pct.columns = [f"{c} (%)" for c in pct.columns]
    return pd.concat([ct, pct], axis=1)


def note_examples(df: pd.DataFrame, n: int = 12, max_len: int = 60) -> list[str]:
    """100 と答えた企業の注釈から短い文言を頻度順に返す（企業名は含めない）。"""
    e = df[(df["pay_gap_all"] == 100) & df["pay_gap_note"].notna()]
    s = e["pay_gap_note"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    s = s[s.str.len() <= max_len]
    return s.value_counts().head(n).index.tolist()


def note_mentions_other_value(df: pd.DataFrame) -> int:
    """100 と答えつつ注釈に 100 以外の％値を書いている企業数（入力制約の疑い）。"""
    e = df[(df["pay_gap_all"] == 100) & df["pay_gap_note"].notna()]
    pat = re.compile(r"(\d{2,3}(?:\.\d+)?)\s*[%％]")
    cnt = 0
    for t in e["pay_gap_note"].astype(str):
        vals = [float(v) for v in pat.findall(t)]
        if any(v != 100 and 20 <= v <= 300 for v in vals):
            cnt += 1
    return cnt


# ---------------------------------------------------------------------------
# 影響
# ---------------------------------------------------------------------------
def impact_on_stats(df: pd.DataFrame) -> pd.DataFrame:
    """ちょうど 100 を除外／含めた場合の統計の違い。"""
    rows = {}
    for col, label in PAY_GAP_COLS.items():
        s = df[col].dropna()
        s_ex = s[s != 100]
        rows[label] = {
            "n（含む）": len(s), "中央値（含む）": s.median(), "平均（含む）": s.mean(),
            "n（除外）": len(s_ex), "中央値（除外）": s_ex.median(), "平均（除外）": s_ex.mean(),
            "90以上の割合（含む）(%)": (s >= 90).mean() * 100,
            "90以上の割合（除外）(%)": (s_ex >= 90).mean() * 100,
        }
    return pd.DataFrame(rows).T.round(2)


def impact_by_size(df: pd.DataFrame, col: str = "pay_gap_all") -> pd.DataFrame:
    d = df[df[col].notna()]
    g_all = d.groupby("size", observed=True)[col]
    g_ex = d[d[col] != 100].groupby("size", observed=True)[col]
    out = pd.DataFrame({
        "n": g_all.size(),
        "中央値（含む）": g_all.median(),
        "中央値（除外）": g_ex.median(),
        "平均（含む）": g_all.mean(),
        "平均（除外）": g_ex.mean(),
    }).round(2)
    out["平均の差"] = (out["平均（含む）"] - out["平均（除外）"]).round(2)
    return out.reindex([s for s in SIZE_ORDER if s in out.index])
