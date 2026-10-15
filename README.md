# gender-gap-disclosure

厚生労働省「[女性の活躍推進企業データベース](https://positive-ryouritsu.mhlw.go.jp/positivedb/)」の
[オープンデータ](https://positive-ryouritsu.mhlw.go.jp/positivedb/opendata/)（企業公表データ）を
ダウンロード → 解凍 → 整形 → 集計し、Markdown レポートと図を生成するリポジトリです。

データは女性活躍推進法に基づき企業が自ら公表している男女の賃金の差異、管理職に占める女性割合、
育児休業取得率などで、全体版は約 6.6 万社・236 列あります。

## 主分析: 賃金差異「ちょうど 100」へのバンチング

男女の賃金の差異（男性=100 としたときの女性賃金）は実績の平均比なので小数になるはずですが、
公表値は **100.0 ちょうど** にスパイク状に集中しています（2026-10-16 時点で 636 社、近傍密度の約 6 倍）。
`gender-gap analyze` が生成する `reports/bunching.md` で、

- スパイクの大きさと他のキリ番（70, 80 など）との比較
- 100 と答えた企業の規模・業種・上場区分
- 正規／非正規の値も 100 か、単一性別の職場か、といった整合性チェック
- 注釈欄の文言分類（「性別による差はつけていない」等、制度上の差の有無と誤解した疑い）
- ちょうど 100 を除外した場合の統計の変化

を扱います。分析ロジックは [bunching.py](src/gender_gap/bunching.py)、
`companies.parquet` には `pay_gap_all_is100` などのフラグ列があり感度分析に使えます。

## セットアップ

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

依存は pandas / pyarrow / matplotlib / certifi（開発用に pytest）のみです。

## 使い方

```bash
# 全部まとめて（ダウンロード → 解凍 → 整形 → レポート）
gender-gap all

# 個別に
gender-gap download            # data/raw/ に ZIP を保存（既にあればスキップ）
gender-gap extract             # data/raw/ に CSV を展開
gender-gap build               # data/processed/ に companies.parquet / kubun.parquet を保存
gender-gap analyze             # reports/bunching.md, reports/report.md, reports/figures/*.png を生成
```

`pip install -e .` をしない場合は `PYTHONPATH=src python3 -m gender_gap <cmd>` か `make all` で同じことができます。

### ダウンロードのオプション

```bash
gender-gap download --dataset 建設業        # 業種別
gender-gap download --dataset 5001人以上    # 企業規模別
gender-gap download --dataset 99 --no-bom   # コード指定、UTF-8 BOM 無し版
gender-gap download --force                 # 再取得
```

データセット名とコードの対応は [config.py](src/gender_gap/config.py) の `DATASET_CODES` にあります。
サイトは一般的なブラウザの User-Agent を要求するため（curl 既定だと 403）、ダウンローダは UA を付けてアクセスします。

既に手元に ZIP がある場合は `data/raw/` に置いて `gender-gap extract` から始められます。

## 生成物

| パス | 内容 |
|---|---|
| `data/raw/*.zip`, `*.csv` | 取得した生データ（git 管理外） |
| `data/processed/companies.parquet` / `.csv` | 1 社 1 行。主要指標を英名に揃え数値化したもの（64 列） |
| `data/processed/kubun.parquet` | 雇用管理区分（最大 5 区分）ごとの項目を縦持ちにしたもの |
| `reports/bunching.md` | 主分析: 賃金差異 100 へのバンチング |
| `reports/report.md` | 全指標の概況レポート |
| `reports/figures/*.png` | レポート内の図 |

### companies.parquet の主な列

| 列 | 元の項目 |
|---|---|
| `name`, `corp_no`, `industry`, `prefecture`, `size`, `market`, `ticker` | 企業名、法人番号、業種、都道府県、企業規模、市場区分、証券コード |
| `pay_gap_all`, `pay_gap_regular`, `pay_gap_nonregular` | 14. 男女の賃金の差異（全労働者／正規／非正規、男性=100） |
| `pay_gap_*_is100`, `pay_gap_note` | 賃金差異がちょうど 100 かのフラグ、注釈・説明欄 |
| `female_manager_pct`, `female_supervisor_pct`, `female_officer_pct` | 10./9./11. 管理職・係長級・役員に占める女性割合 |
| `female_worker_pct`, `female_hire_pct` | 3./1. 労働者・採用者に占める女性割合（雇用管理区分 1） |
| `parental_leave_male_pct`, `parental_leave_female_pct` | 5. 育児休業取得率（雇用管理区分 1） |
| `tenure_male`, `tenure_female`, `tenure_gap_years` | 4.(1) 平均継続勤務年数と男女差 |
| `overtime_hours`, `paid_leave_pct` | 6. 平均残業時間、8.(1) 有給取得率 |
| `has_eruboshi`, `has_kurumin`, `has_platinum_*`, `has_nadeshiko` | 各認定の有無（bool） |
| `sys_*`, `n_systems` | 両立支援制度の有無（bool）と導入数 |
| `listed`, `prime` | 市場区分あり／東証プライム |

区分 2〜5 の値が必要な場合は `kubun.parquet`（`row_id` で `companies` と結合）を使ってください。

## レポートの内容

### bunching.md（主分析）

要約 → 分布の形（細かいヒストグラム、キリ番の超過倍率） → 誰が 100 と答えているか →
整合性チェック → 注釈欄の文言 → 全体統計への影響 → 解釈と推奨

### report.md（概況）

1. データ概要（企業数、規模・業種の内訳、認定数）
2. 指標ごとの公表率（全体／企業規模別）と除外した異常値の件数
3. 主要指標の全体分布
4. 男女の賃金の差異（分布帯、企業規模別、雇用形態別、業種別、都道府県別）
5. 女性の登用（管理職・役員の割合、業種別、女性労働者割合との関係）
6. 育児休業取得率（企業規模別、業種別）
7. 働き方（残業・有給・継続勤務年数差、両立支援制度の導入率）
8. 上場区分・えるぼし／くるみん認定との関係（企業規模別に比較）
9. 指標間の Spearman 相関
10. 雇用管理区分名の内訳

### データ扱い上の注意

- すべて企業の自己申告値で、集計期間・対象範囲（単体／連結）は企業ごとに異なります。
- 入力ミスとみなす値（賃金差異 > 200%、取得率 > 100% など）は集計から除外しています。
  しきい値は [config.py](src/gender_gap/config.py) の `PAY_GAP_MAX_PLAUSIBLE` と
  [analysis.py](src/gender_gap/analysis.py) の `plausible()` で変更できます。
- 公表は任意項目が多く、規模が小さい企業ほど未記入が多いため、規模をまたいだ比較は公表率も併せて見てください。
- 生 CSV は同名列を含みます（雇用管理区分 1〜5 の繰り返し）。pandas は 2 列目以降に `.1` `.2` … を付けるので、
  [load.py](src/gender_gap/load.py) はその規則に合わせて区分ごとの列を取り出しています。

## 分析を追加する

バンチング関連は `src/gender_gap/bunching.py`、それ以外は `src/gender_gap/analysis.py` に
DataFrame を受け取って DataFrame を返す関数を足し、

`src/gender_gap/report.py` の `build_bunching_report()` / `build_report()` から呼んで `md_table()` で出力するのが最短です。
対話的に触るなら:

```python
from gender_gap.load import load_processed
from gender_gap import analysis as A

from gender_gap import bunching as B

companies, kubun = load_processed()
df = A.plausible(companies)
B.excess_mass(df, "pay_gap_all")          # キリ番ごとの超過倍率
A.summarize(df[~df["pay_gap_all_is100"]], "pay_gap_all", "industry")  # 100 を除いた業種別
```

## テスト

```bash
pytest -q
```

テストは合成した 60 行のフィクスチャ（`tests/fixtures/sample_utf8_bom.csv`、実在企業は含みません）で動くため、
データのダウンロードは不要です。

## 出典・利用規約

出典：女性の活躍推進企業データベースオープンデータ（https://positive-ryouritsu.mhlw.go.jp/positivedb/opendata/）を加工して作成

データは[利用規約](https://positive-ryouritsu.mhlw.go.jp/positivedb/opendata/riyoukiyaku.html)
（政府標準利用規約 2.0 準拠、CC BY 4.0 互換）に従って利用してください。
加工して公開する場合は、出典と加工した旨の記載が必要です。
