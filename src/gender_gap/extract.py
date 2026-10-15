"""ZIP の解凍。"""

from __future__ import annotations

import zipfile
from pathlib import Path

from .config import RAW_DIR


def find_latest_zip(raw_dir: Path = RAW_DIR, pattern: str = "*.zip") -> Path:
    zips = sorted(raw_dir.glob(pattern))
    if not zips:
        raise FileNotFoundError(f"{raw_dir} に ZIP がありません。先に download を実行してください。")
    return zips[-1]


def extract(zip_path: Path | None = None, out_dir: Path = RAW_DIR) -> list[Path]:
    """ZIP を解凍し、取り出した CSV のパス一覧を返す。"""
    zip_path = zip_path or find_latest_zip(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = out_dir / Path(info.filename).name  # ディレクトリ階層は無視
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            extracted.append(target)
    return extracted


def find_latest_csv(raw_dir: Path = RAW_DIR) -> Path:
    csvs = sorted(raw_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"{raw_dir} に CSV がありません。先に extract を実行してください。")
    return csvs[-1]
