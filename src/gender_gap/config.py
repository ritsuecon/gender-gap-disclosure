"""パス・URL・データセットコードなどの設定。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORT_DIR = ROOT / "reports"
FIGURE_DIR = REPORT_DIR / "figures"

BASE_URL = "https://positive-ryouritsu.mhlw.go.jp/positivedb/opendata/"
TERMS_URL = BASE_URL + "riyoukiyaku.html"

# サイトは一般的な UA を要求する（curl 既定 UA では 403）
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

# ダウンロードエンドポイント。w= にデータセットコードを渡すと ZIP 本体が返る。
#   download_b.html  : UTF-8 BOM 有り（Excel 向け）
#   download_nb.html : UTF-8 BOM 無し
DOWNLOAD_PATH_BOM = "download_b.html"
DOWNLOAD_PATH_NOBOM = "download_nb.html"

# データセットコード（2026-10-16 時点のページから採取）
DATASET_CODES: dict[str, int] = {
    "全体版": 99,
    # 企業規模別
    "5001人以上": 57,
    "1001人～5000人": 56,
    "501人～1000人": 55,
    "301人～500人": 54,
    "101人～300人": 53,
    "10～100人": 52,
    "10人未満": 51,
    # 業種別
    "農業、林業": 1,
    "漁業": 2,
    "鉱業、採石業、砂利採取業": 3,
    "建設業": 4,
    "食料品、飲料・たばこ・飼料製造業": 5,
    "繊維工業": 6,
    "木材・木製品、家具・装備品製造業": 7,
    "パルプ・紙・紙加工品製造業、印刷業・印刷関連業": 8,
    "化学工業": 9,
    "石油製品・石炭製品製造業": 10,
    "プラスチック製品製造業、ゴム製品製造業": 11,
    "鉄鋼業、非鉄金属・金属製品製造業": 12,
    "業務用機械器具製造業": 13,
    "情報通信機械器具製造業": 14,
    "輸送用機械器具製造業": 15,
    "その他製造業": 16,
    "電気・ガス・熱供給・水道業": 17,
    "情報通信業": 18,
    "報道": 19,
    "運輸業、郵便業": 20,
    "卸売業、小売業": 21,
    "金融業、保険業": 22,
    "不動産業、物品賃貸業": 23,
    "学術研究、専門・技術サービス業": 24,
    "宿泊業、飲食サービス業": 25,
    "生活関連サービス業、娯楽業": 26,
    "教育、学習支援業": 27,
    "医療、福祉": 28,
    "複合サービス事業": 29,
    "サービス業（他に分類されないもの）": 30,
    "公務（他に分類されるものを除く）": 31,
    "分類不能の産業": 32,
}

# 企業規模の表示順
SIZE_ORDER = [
    "10人未満",
    "10～100人",
    "101～300人",
    "301～500人",
    "501～1000人",
    "1001～5000人",
    "5001人以上",
]

# 男女の賃金の差異(%) はこの値を超えると入力ミスとみなして統計から除外する
PAY_GAP_MAX_PLAUSIBLE = 200.0


def download_url(code: int = 99, bom: bool = True) -> str:
    path = DOWNLOAD_PATH_BOM if bom else DOWNLOAD_PATH_NOBOM
    return f"{BASE_URL}{path}?w={code}"
