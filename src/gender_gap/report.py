"""Markdown レポートと図の生成。"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from . import analysis as A  # noqa: E402
from .config import BASE_URL, FIGURE_DIR, REPORT_DIR, SIZE_ORDER  # noqa: E402

JP_FONT_CANDIDATES = [
    "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans CJK JP", "Noto Sans JP",
    "IPAexGothic", "IPAGothic", "Yu Gothic", "Meiryo", "TakaoGothic", "VL Gothic",
]


def setup_fonts() -> str | None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in JP_FONT_CANDIDATES:
        if name in available:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return name
    return None


# ---------------------------------------------------------------------------
# Markdown ユーティリティ（tabulate 非依存）
# ---------------------------------------------------------------------------
def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return ""
    if isinstance(v, float):
        return f"{v:,.1f}"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int) or (hasattr(v, "is_integer") and not isinstance(v, float)):
        return f"{int(v):,}"
    return str(v)


def md_table(df: pd.DataFrame, index_label: str = "") -> str:
    df = df.copy()
    # 件数列など「全て整数の float 列」は整数として表示する
    for c in df.columns:
        col = df[c]
        if pd.api.types.is_float_dtype(col) and col.dropna().apply(float.is_integer).all() and col.notna().any():
            df[c] = col.astype("Int64")
    cols = [index_label] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    # object 化してから行を回す（iterrows は int 列を float に昇格させてしまう）
    for idx, row in df.astype(object).iterrows():
        lines.append("| " + " | ".join([_fmt(idx)] + [_fmt(v) for v in row.tolist()]) + " |")
    return "\n".join(lines)


def md_kv(d: dict) -> str:
    return "\n".join(f"- {k}: {_fmt(v)}" for k, v in d.items())


# ---------------------------------------------------------------------------
# 図
# ---------------------------------------------------------------------------
def _save(fig, name: str, fig_dir: Path) -> str:
    fig_dir.mkdir(parents=True, exist_ok=True)
    path = fig_dir / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return f"figures/{name}.png"


def fig_hist(df: pd.DataFrame, col: str, title: str, name: str, fig_dir: Path, xlabel: str) -> str:
    s = df[col].dropna()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(s, bins=60, color="#4C72B0", edgecolor="white")
    ax.axvline(s.median(), color="#C44E52", linestyle="--", label=f"中央値 {s.median():.1f}")
    ax.set_title(f"{title}（n={len(s):,}）")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("社数")
    ax.legend()
    return _save(fig, name, fig_dir)


def fig_box_by_size(df: pd.DataFrame, col: str, title: str, name: str, fig_dir: Path, ylabel: str) -> str:
    groups = [df.loc[df["size"] == s, col].dropna() for s in SIZE_ORDER]
    labels = [f"{s}\n(n={len(g):,})" for s, g in zip(SIZE_ORDER, groups)]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.boxplot(groups, tick_labels=labels, showfliers=False, medianprops={"color": "#C44E52"})
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, name, fig_dir)


def fig_bar_median(summary: pd.DataFrame, title: str, name: str, fig_dir: Path, xlabel: str,
                   ref: float | None = None) -> str:
    s = summary.sort_values("中央値")
    fig, ax = plt.subplots(figsize=(9, max(4, 0.32 * len(s) + 1)))
    ax.barh([f"{i} (n={int(n):,})" for i, n in zip(s.index, s["n"])], s["中央値"], color="#4C72B0")
    if ref is not None:
        ax.axvline(ref, color="#C44E52", linestyle="--", label=f"全体中央値 {ref:.1f}")
        ax.legend(loc="lower right")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", alpha=0.3)
    return _save(fig, name, fig_dir)


def fig_scatter(df: pd.DataFrame, x: str, y: str, title: str, name: str, fig_dir: Path, xlabel: str, ylabel: str) -> str:
    d = df[[x, y]].dropna()
    fig, ax = plt.subplots(figsize=(7, 5.5))
    hb = ax.hexbin(d[x], d[y], gridsize=45, cmap="Blues", mincnt=1)
    fig.colorbar(hb, ax=ax, label="社数")
    rho = d[x].corr(d[y], method="spearman")
    ax.set_title(f"{title}（n={len(d):,}, Spearman ρ={rho:.2f}）")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    return _save(fig, name, fig_dir)


# ---------------------------------------------------------------------------
# レポート本体
# ---------------------------------------------------------------------------
def build_report(companies: pd.DataFrame, kubun: pd.DataFrame, source_date: str | None,
                 report_dir: Path = REPORT_DIR, fig_dir: Path = FIGURE_DIR) -> Path:
    font = setup_fonts()
    report_dir.mkdir(parents=True, exist_ok=True)
    raw = companies
    df = A.plausible(companies)
    date_label = source_date or "取得日不明"

    md: list[str] = []
    md.append("# 女性の活躍推進企業データベース オープンデータ 分析レポート\n")
    md.append(f"出典：女性の活躍推進企業データベースオープンデータ（{date_label}時点）（{BASE_URL}）を加工して作成\n")
    if font is None:
        md.append("> 注: 日本語フォントが見つからなかったため、図中の日本語が欠ける場合があります。\n")

    # 1. 概要
    md.append("## 1. データ概要\n")
    md.append(md_kv(A.overview(raw)))
    md.append("\n### 企業規模の内訳\n")
    size_counts = raw["size"].value_counts(sort=False).rename("企業数").to_frame()
    size_counts["構成比(%)"] = (size_counts["企業数"] / len(raw) * 100).round(1)
    md.append(md_table(size_counts, "企業規模"))
    md.append("\n### 業種の内訳（上位 15）\n")
    ind = raw["industry"].value_counts().head(15).rename("企業数").to_frame()
    ind["構成比(%)"] = (ind["企業数"] / len(raw) * 100).round(1)
    md.append(md_table(ind, "業種"))

    # 2. 公表率
    md.append("\n## 2. 指標の公表率\n")
    md.append("各指標は任意公表のため、企業によって公表項目が異なる。以下は値が入力されている企業の割合。\n")
    md.append(md_table(A.disclosure_rates(raw), "指標"))
    md.append("\n### 企業規模別の公表率 (%)\n")
    md.append(md_table(A.disclosure_rates(raw, "size"), "企業規模"))
    md.append("\n### 統計から除外した異常値\n")
    md.append("入力ミスとみなし、以降の集計では NaN 扱いにした件数。\n")
    md.append(md_table(A.implausible_counts(raw).set_index("指標"), "指標"))

    # 3. 全体統計
    md.append("\n## 3. 主要指標の全体分布\n")
    md.append(md_table(A.overall_stats(df), "指標"))

    # 4. 賃金差異
    md.append("\n## 4. 男女の賃金の差異\n")
    md.append("男性の賃金を 100 としたときの女性の賃金（%）。100 未満は女性が低い。\n")
    med_all = df["pay_gap_all"].median()
    md.append(f"![]({fig_hist(df, 'pay_gap_all', '男女の賃金の差異（全労働者）', 'pay_gap_hist', fig_dir, '女性賃金 / 男性賃金 (%)')})\n")
    md.append("### 分布帯\n")
    md.append(md_table(A.pay_gap_bands(df), "帯 (%)"))
    md.append("\n### 企業規模別\n")
    md.append(md_table(A.summarize(df, "pay_gap_all", "size"), "企業規模"))
    md.append(f"\n![]({fig_box_by_size(df, 'pay_gap_all', '男女の賃金の差異（全労働者）: 企業規模別', 'pay_gap_by_size', fig_dir, '%')})\n")
    md.append("### 雇用形態別\n")
    md.append(md_table(A.overall_stats(df).loc[[A.INDICATORS[c] for c in A.PAY_GAP_COLS]], "指標"))
    md.append("\n### 業種別（n≥30）\n")
    ind_pg = A.summarize(df, "pay_gap_all", "industry")
    md.append(md_table(ind_pg, "業種"))
    md.append(f"\n![]({fig_bar_median(ind_pg, '男女の賃金の差異（全労働者）: 業種別中央値', 'pay_gap_by_industry', fig_dir, '%', ref=med_all)})\n")
    md.append("### 都道府県別（上位・下位 10）\n")
    pref_pg = A.summarize(df, "pay_gap_all", "prefecture")
    low, high = A.top_bottom(pref_pg, 10)
    md.append("差異が大きい（女性賃金が低い）都道府県:\n")
    md.append(md_table(low, "都道府県"))
    md.append("\n差異が小さい都道府県:\n")
    md.append(md_table(high, "都道府県"))

    # 5. 女性管理職
    md.append("\n## 5. 女性の登用（係長級・管理職・役員）\n")
    md.append("### 企業規模別 管理職に占める女性割合\n")
    md.append(md_table(A.summarize(df, "female_manager_pct", "size"), "企業規模"))
    md.append(f"\n![]({fig_box_by_size(df, 'female_manager_pct', '管理職に占める女性割合: 企業規模別', 'manager_by_size', fig_dir, '%')})\n")
    md.append("### 企業規模別 役員に占める女性割合\n")
    md.append(md_table(A.summarize(df, "female_officer_pct", "size"), "企業規模"))
    md.append("\n### 業種別 管理職に占める女性割合（n≥30）\n")
    ind_mg = A.summarize(df, "female_manager_pct", "industry")
    md.append(md_table(ind_mg, "業種"))
    md.append(f"\n![]({fig_bar_median(ind_mg, '管理職に占める女性割合: 業種別中央値', 'manager_by_industry', fig_dir, '%', ref=df['female_manager_pct'].median())})\n")
    md.append("### 女性労働者割合と女性管理職割合の関係\n")
    md.append(f"![]({fig_scatter(df, 'female_worker_pct', 'female_manager_pct', '女性労働者割合 vs 女性管理職割合', 'worker_vs_manager', fig_dir, '労働者に占める女性割合 (%)', '管理職に占める女性割合 (%)')})\n")
    md.append("### 女性管理職割合と賃金差異の関係\n")
    md.append(f"![]({fig_scatter(df, 'female_manager_pct', 'pay_gap_all', '女性管理職割合 vs 賃金差異', 'manager_vs_pay_gap', fig_dir, '管理職に占める女性割合 (%)', '女性賃金 / 男性賃金 (%)')})\n")

    # 6. 育休
    md.append("\n## 6. 育児休業取得率\n")
    md.append("### 企業規模別 男性の育児休業取得率\n")
    md.append(md_table(A.summarize(df, "parental_leave_male_pct", "size"), "企業規模"))
    md.append(f"\n![]({fig_box_by_size(df, 'parental_leave_male_pct', '男性の育児休業取得率: 企業規模別', 'male_leave_by_size', fig_dir, '%')})\n")
    md.append("### 業種別 男性の育児休業取得率（n≥30）\n")
    ind_pl = A.summarize(df, "parental_leave_male_pct", "industry")
    md.append(md_table(ind_pl, "業種"))
    md.append(f"\n![]({fig_bar_median(ind_pl, '男性の育児休業取得率: 業種別中央値', 'male_leave_by_industry', fig_dir, '%', ref=df['parental_leave_male_pct'].median())})\n")

    # 7. 働き方
    md.append("\n## 7. 働き方（残業・有給・継続勤務）\n")
    md.append("### 企業規模別 一月当たり平均残業時間\n")
    md.append(md_table(A.summarize(df, "overtime_hours", "size"), "企業規模"))
    md.append("\n### 企業規模別 年次有給休暇取得率\n")
    md.append(md_table(A.summarize(df, "paid_leave_pct", "size"), "企業規模"))
    md.append("\n### 企業規模別 平均継続勤務年数の男女差（男性−女性）\n")
    md.append(md_table(A.summarize(df, "tenure_gap_years", "size"), "企業規模"))
    md.append("\n### 両立支援制度の導入率 (%)\n")
    md.append(md_table(A.system_adoption(raw), "企業規模"))

    # 8. 上場・認定
    md.append("\n## 8. 上場区分・認定との関係\n")
    md.append("### 上場区分別の中央値\n")
    md.append(md_table(A.listed_comparison(df), "区分"))
    md.append("\n### えるぼし認定の有無と賃金差異（企業規模別中央値）\n")
    md.append(md_table(A.certification_effect(df, "has_eruboshi", "pay_gap_all"), "企業規模"))
    md.append("\n### えるぼし認定の有無と女性管理職割合（企業規模別中央値）\n")
    md.append(md_table(A.certification_effect(df, "has_eruboshi", "female_manager_pct"), "企業規模"))
    md.append("\n### くるみん認定の有無と男性育休取得率（企業規模別中央値）\n")
    md.append(md_table(A.certification_effect(df, "has_kurumin", "parental_leave_male_pct"), "企業規模"))

    # 9. 相関
    md.append("\n## 9. 指標間の相関（Spearman）\n")
    md.append(md_table(A.correlations(df), ""))

    # 10. 区分
    md.append("\n## 10. 雇用管理区分の内訳\n")
    md.append("企業が自由に定義する区分名の上位（賃金差異以外の指標は区分ごとに公表される）。\n")
    kub = kubun.loc[kubun["section"] == "female_worker_pct", "kubun"].value_counts().head(15).rename("件数").to_frame()
    md.append(md_table(kub, "区分名"))

    md.append("\n---\n")
    md.append("本レポートは `python -m gender_gap analyze` により自動生成。数値は企業の自己申告値であり、集計期間・対象範囲は企業ごとに異なる。\n")

    out = report_dir / "report.md"
    out.write_text("\n".join(md), encoding="utf-8")
    return out


# ===========================================================================
# バンチング（賃金差異 = 100 への集中）レポート
# ===========================================================================
from . import bunching as B  # noqa: E402


def fig_fine_hist(df: pd.DataFrame, col: str, title: str, name: str, fig_dir: Path,
                  lo: float, hi: float, width: float) -> str:
    h = B.fine_histogram(df, col, lo=lo, hi=hi, width=width)
    is100 = (h["bin_left"] <= 100) & (h["bin_left"] + width > 100)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.bar(h["bin_left"], h["count"], width=width, align="edge",
           color=["#C44E52" if f else "#4C72B0" for f in is100], edgecolor="white", linewidth=0.3)
    n100 = int((df[col] == 100).sum())
    ax.annotate(f"ちょうど 100.0: {n100:,} 社", xy=(100, h.loc[is100, "count"].max()),
                xytext=(100 + (hi - lo) * 0.08, h["count"].max() * 0.85),
                arrowprops={"arrowstyle": "->", "color": "#C44E52"}, color="#C44E52")
    ax.set_title(f"{title}（{lo:g}〜{hi:g}, {width:g} 刻み）")
    ax.set_xlabel("女性賃金 / 男性賃金 (%)")
    ax.set_ylabel("社数")
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, name, fig_dir)


def fig_excess(df: pd.DataFrame, name: str, fig_dir: Path) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), sharey=True)
    for ax, (col, label) in zip(axes, B.PAY_GAP_COLS.items()):
        em = B.excess_mass(df, col)
        colors = ["#C44E52" if v == 100 else "#4C72B0" for v in em.index]
        ax.bar([str(v) for v in em.index], em["超過倍率"], color=colors)
        ax.axhline(1, color="gray", linestyle="--", linewidth=0.8)
        ax.set_title(label)
        ax.set_xlabel("値")
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("超過倍率（ちょうどの社数 / 近傍密度）")
    fig.suptitle("キリ番へのバンチング: 100 だけが突出している")
    return _save(fig, name, fig_dir)


def fig_three_panels(df: pd.DataFrame, name: str, fig_dir: Path) -> str:
    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)
    for ax, (col, label) in zip(axes, B.PAY_GAP_COLS.items()):
        h = B.fine_histogram(df, col, lo=40, hi=140, width=1.0)
        is100 = h["bin_left"] == 100
        ax.bar(h["bin_left"], h["count"], width=1.0, align="edge",
               color=["#C44E52" if f else "#4C72B0" for f in is100], edgecolor="white", linewidth=0.3)
        ax.set_title(f"{label}（n={int(df[col].notna().sum()):,}, ちょうど100={int((df[col] == 100).sum()):,}）", fontsize=10)
        ax.set_ylabel("社数")
        ax.grid(axis="y", alpha=0.3)
    axes[-1].set_xlabel("女性賃金 / 男性賃金 (%)  1 刻み")
    return _save(fig, name, fig_dir)


def fig_share_by_size(df: pd.DataFrame, name: str, fig_dir: Path) -> str:
    s = B.share_by(df, "size", min_n=1)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar([f"{i}\n(n={int(n):,})" for i, n in zip(s.index, s["公表社数"])], s["割合(%)"], color="#4C72B0")
    ax.set_title("賃金差異をちょうど 100 と公表した企業の割合: 企業規模別")
    ax.set_ylabel("%")
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, name, fig_dir)


def build_bunching_report(companies: pd.DataFrame, source_date: str | None,
                          report_dir: Path = REPORT_DIR, fig_dir: Path = FIGURE_DIR) -> Path:
    setup_fonts()
    report_dir.mkdir(parents=True, exist_ok=True)
    df = A.plausible(companies)
    date_label = source_date or "取得日不明"
    s = df["pay_gap_all"].dropna()
    n100 = int((s == 100).sum())
    em = B.excess_mass(df, "pay_gap_all")
    ratio100 = em.loc[100, "超過倍率"]
    win = B.window_counts(df)

    md: list[str] = []
    md.append("# 男女の賃金の差異「ちょうど 100」へのバンチング分析\n")
    md.append(f"出典：女性の活躍推進企業データベースオープンデータ（{date_label}時点）（{BASE_URL}）を加工して作成\n")
    md.append("## 要約\n")
    md.append(
        f"- 男女の賃金の差異（全労働者）を公表した {len(s):,} 社のうち {n100:,} 社（{n100 / len(s) * 100:.1f}%）が"
        f"**ちょうど 100.0** を記入している。\n"
        f"- 100 の近傍（±2.5）の密度は 1 ポイント当たり {em.loc[100, '近傍の密度（社/1pt）']:.0f} 社なので、"
        f"ちょうど 100 は近傍の **{ratio100:.0f} 倍** のスパイク。他のキリ番（70, 80 など）の超過倍率は"
        f" {em.drop(100)['超過倍率'].max():.1f} 倍以下で、100 だけが別格。\n"
        f"- 99.5〜100.5 の帯には {int(((s >= 99.5) & (s < 100.5)).sum()):,} 社いるが、そのうち {n100:,} 社が 100.0 ちょうど。"
        f"「ほぼ同額」ではなく「同額と宣言している」値である。\n"
        "- 100 と答えた企業は、小規模・非上場に多く、注釈欄に「男女で賃金に差はない」「性別による差はつけていない」と"
        "**制度上の差の有無**を書いているケースが目立つ。指標の定義（平均賃金の実績比）とは別の解釈で記入された疑いが強い。\n"
        "- 全体の中央値・平均への影響は小さい（下表）が、「90 以上」の割合や小規模企業の平均は 100 を含めるかで動く。"
        "賃金差異を分析する際は `pay_gap_all_is100` フラグで感度分析することを勧める。\n"
    )

    md.append("## 1. 分布の形\n")
    md.append(f"![]({fig_fine_hist(df, 'pay_gap_all', '男女の賃金の差異（全労働者）', 'bunch_hist_70_130', fig_dir, 70, 130, 0.5)})\n")
    md.append(f"![]({fig_fine_hist(df, 'pay_gap_all', '男女の賃金の差異（全労働者）拡大', 'bunch_hist_95_105', fig_dir, 95, 105, 0.1)})\n")
    md.append("### 100 周辺の帯別社数\n")
    md.append(md_table(win, "帯"))
    md.append("\n### キリ番ごとの超過倍率（全労働者）\n")
    md.append("近傍密度 = ±2.5 ポイント（その値自身を除く）の社数 ÷ 5。値が小数 1 桁で滑らかに分布していれば、"
              "ちょうどその値になる社数は近傍密度の 1/10 程度が期待値。\n")
    md.append(md_table(em, "値"))
    md.append(f"\n![]({fig_excess(df, 'bunch_excess_ratio', fig_dir)})\n")
    md.append("### 雇用形態別の丸めの度合い\n")
    md.append(md_table(B.rounding_shares(df), "対象"))
    md.append(f"\n![]({fig_three_panels(df, 'bunch_three_panels', fig_dir)})\n")

    md.append("## 2. どの企業が 100 と答えているか\n")
    md.append("### 企業規模別\n")
    md.append(md_table(B.share_by(df, "size"), "企業規模"))
    md.append(f"\n![]({fig_share_by_size(df, 'bunch_share_by_size', fig_dir)})\n")
    md.append("### 上場・非上場\n")
    md.append(md_table(B.share_listed(df), "区分"))
    md.append("\n### 業種別（公表 100 社以上、割合の高い順）\n")
    md.append(md_table(B.share_by(df, "industry"), "業種"))
    md.append("\n### 都道府県別（公表 100 社以上、上位 10）\n")
    md.append(md_table(B.share_by(df, "prefecture").head(10), "都道府県"))

    md.append("\n## 3. 整合性チェック\n")
    md.append("### 正規・非正規の値も 100 か\n")
    md.append(md_table(B.consistency(df), "項目"))
    md.append("\n正規・非正規・全体の 3 つが同時にちょうど 100 になるのは、実績の比としてはほぼあり得ない。"
              "3 つとも 100 の企業は「差異なし」と宣言している可能性が高い。\n")
    md.append("### 単一性別の職場か（女性労働者割合・区分 1）\n")
    md.append("女性または男性が 0 人なら比は定義できない。そうした企業が便宜的に 100 を置いているかを見る。\n")
    md.append(md_table(B.single_sex_profile(df), "女性労働者割合"))
    md.append("\n### 他の指標との比較\n")
    md.append(md_table(B.manager_profile(df), "グループ"))

    md.append("\n## 4. 注釈欄の文言\n")
    md.append("注釈欄（14. 男女の賃金の差異 注釈・説明）を正規表現で分類した。\n")
    md.append(md_table(B.note_classification(df), "分類"))
    other = B.note_mentions_other_value(df)
    md.append(f"\n100 と記入しつつ注釈に 100 以外の％値（20〜300）を書いている企業: {other} 社。"
              "入力欄の制約や誤入力で実際の値が反映されていない可能性がある。\n")
    md.append("### 100 と答えた企業の注釈の典型例（頻度順、60 文字以内）\n")
    for t in B.note_examples(df):
        md.append(f"- {t}")

    md.append("\n## 5. 全体統計への影響\n")
    md.append("### ちょうど 100 を含む／除外した統計\n")
    md.append(md_table(B.impact_on_stats(df), "対象"))
    md.append("\n### 企業規模別（全労働者）\n")
    md.append(md_table(B.impact_by_size(df), "企業規模"))

    md.append("\n## 6. 解釈と推奨\n")
    md.append(
        "**考えられる原因**\n\n"
        "1. 指標の誤解: 「男女の賃金の差異」を、賃金規程に性別による差があるか（ない → 100）と解釈して記入している。"
        "注釈欄の文言（「性別による差はつけていない」等）がこれを裏付ける。\n"
        "2. 計算不能の代替値: 一方の性別が 0 人、あるいは少人数で平均比を出す意味がない企業が 100 を置いている。"
        "女性労働者割合が 0% または 100% の企業が「ちょうど 100」群に多いことと整合する。\n"
        "3. 丸め: 99.6 などを 100 に丸めた企業も一部含まれるが、99.5〜100.5 の帯の中で 100.0 ちょうどの比率が極端に高く、"
        "丸めだけでは説明できない。\n\n"
        "**分析上の推奨**\n\n"
        "- 賃金差異を使う分析では `pay_gap_all_is100`（正規・非正規は `pay_gap_regular_is100` 等）で感度分析する。\n"
        "- 特に従業員 300 人以下や非上場を対象にする場合、100 の群を除くか別扱いにする。\n"
        "- 「100 超（女性が高い）」の割合を論じる際は、100 ちょうどを含めないよう帯の境界に注意する。\n"
        "- 本レポートの数値は自己申告値であり、個社の記入意図を確認したものではない。\n"
    )
    md.append("\n---\n")
    md.append("本レポートは `python -m gender_gap analyze` により自動生成。\n")

    out = report_dir / "bunching.md"
    out.write_text("\n".join(md), encoding="utf-8")
    return out
