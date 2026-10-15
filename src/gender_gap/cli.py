"""コマンドラインインターフェース。

    python -m gender_gap download [--dataset 全体版] [--no-bom] [--force]
    python -m gender_gap extract  [--zip PATH]
    python -m gender_gap build    [--csv PATH]
    python -m gender_gap analyze
    python -m gender_gap all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import extract as X
from . import load as L
from .config import DATASET_CODES, PROCESSED_DIR, RAW_DIR, REPORT_DIR
from .download import download


def cmd_download(args) -> Path:
    path = download(args.dataset, bom=not args.no_bom, force=args.force)
    print(f"downloaded: {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)")
    return path


def cmd_extract(args) -> list[Path]:
    paths = X.extract(Path(args.zip) if args.zip else None)
    for p in paths:
        print(f"extracted: {p}")
    return paths


def cmd_build(args) -> None:
    csv = Path(args.csv) if args.csv else X.find_latest_csv()
    print(f"loading: {csv}")
    raw = L.load_raw(csv)
    companies = L.build_companies(raw)
    kubun = L.build_kubun(raw)
    paths = L.save_processed(companies, kubun)
    (PROCESSED_DIR / "SOURCE").write_text(f"{csv.name}\n{L.source_date_from_filename(csv) or ''}\n")
    print(f"companies: {companies.shape}, kubun: {kubun.shape}")
    for k, p in paths.items():
        print(f"saved: {p}")


def cmd_analyze(args) -> Path:
    from .report import build_bunching_report, build_report

    companies, kubun = L.load_processed()
    src = PROCESSED_DIR / "SOURCE"
    source_date = src.read_text().splitlines()[1] if src.exists() else None
    out_b = build_bunching_report(companies, source_date or None)
    print(f"report (main): {out_b}")
    out = build_report(companies, kubun, source_date or None)
    print(f"report: {out}")
    return out_b


def cmd_all(args) -> None:
    cmd_download(args)
    cmd_extract(args)
    cmd_build(args)
    cmd_analyze(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gender-gap", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def add_download_opts(sp):
        sp.add_argument("--dataset", default="全体版", help=f"データセット名またはコード。候補: {', '.join(DATASET_CODES)}")
        sp.add_argument("--no-bom", action="store_true", help="UTF-8 BOM 無し版を取得する")
        sp.add_argument("--force", action="store_true", help="既存ファイルがあっても再取得する")

    def add_extract_opts(sp):
        sp.add_argument("--zip", default=None, help=f"解凍する ZIP（省略時は {RAW_DIR} の最新）")

    def add_build_opts(sp):
        sp.add_argument("--csv", default=None, help=f"整形する CSV（省略時は {RAW_DIR} の最新）")

    sp = sub.add_parser("download", help="ZIP をダウンロード"); add_download_opts(sp); sp.set_defaults(func=cmd_download)
    sp = sub.add_parser("extract", help="ZIP を解凍"); add_extract_opts(sp); sp.set_defaults(func=cmd_extract)
    sp = sub.add_parser("build", help="CSV を整形して parquet に保存"); add_build_opts(sp); sp.set_defaults(func=cmd_build)
    sp = sub.add_parser("analyze", help=f"レポート（bunching.md, report.md）を {REPORT_DIR} に生成"); sp.set_defaults(func=cmd_analyze)
    sp = sub.add_parser("all", help="download → extract → build → analyze")
    add_download_opts(sp); add_extract_opts(sp); add_build_opts(sp); sp.set_defaults(func=cmd_all)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0
