"""オープンデータ ZIP のダウンロード。"""

from __future__ import annotations

import re
import shutil
import urllib.request
from pathlib import Path

from .config import DATASET_CODES, RAW_DIR, USER_AGENT, download_url


def resolve_code(dataset: str | int) -> int:
    """'全体版' / '建設業' / 99 などをデータセットコードに変換する。"""
    if isinstance(dataset, int):
        return dataset
    if dataset.isdigit():
        return int(dataset)
    try:
        return DATASET_CODES[dataset]
    except KeyError as exc:
        raise ValueError(f"未知のデータセット名: {dataset!r}。候補: {list(DATASET_CODES)}") from exc


def _filename_from_headers(headers, fallback: str) -> str:
    cd = headers.get("Content-Disposition", "") or ""
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', cd)
    return m.group(1) if m else fallback


def download(dataset: str | int = "全体版", bom: bool = True, out_dir: Path = RAW_DIR, force: bool = False) -> Path:
    """ZIP をダウンロードして保存先パスを返す。既存ファイルがあれば再利用する。"""
    code = resolve_code(dataset)
    url = download_url(code, bom=bom)
    out_dir.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        ctype = resp.headers.get("Content-Type", "")
        if "octet-stream" not in ctype and "zip" not in ctype:
            raise RuntimeError(f"ZIP ではない応答を受信しました: {url} Content-Type={ctype}")
        suffix = "utf8_bom" if bom else "utf8"
        name = _filename_from_headers(resp.headers, f"{code}_{suffix}.zip")
        dest = out_dir / name
        if dest.exists() and not force:
            return dest
        tmp = dest.with_suffix(".zip.part")
        with open(tmp, "wb") as fh:
            shutil.copyfileobj(resp, fh)
        tmp.replace(dest)
    return dest
