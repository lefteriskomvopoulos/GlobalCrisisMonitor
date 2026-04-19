"""GDELT data ingestion: download + unzip the public 15-min event exports."""
from __future__ import annotations

import datetime as dt
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from config import DOWNLOAD_DIR, GDELT_MASTER_URL, UNZIPPED_DIR


def _fetch_master_list() -> list[str]:
    resp = requests.get(GDELT_MASTER_URL, timeout=30)
    resp.raise_for_status()
    return [line.split(" ")[2] for line in resp.text.splitlines()
            if "export.CSV.zip" in line]


def _download_one(url: str, dest_dir: Path) -> Path | None:
    fname = url.split("/")[-1]
    out = dest_dir / fname
    if out.exists() and out.stat().st_size > 0:
        return out
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        out.write_bytes(r.content)
        return out
    except Exception as exc:
        print(f"  ! failed {fname}: {exc}")
        return None


def _unzip_one(zip_path: Path, dest_dir: Path) -> int:
    extracted = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                target = dest_dir / member
                if not target.exists():
                    zf.extract(member, dest_dir)
                    extracted += 1
    except zipfile.BadZipFile:
        print(f"  ! corrupt zip removed: {zip_path.name}")
        zip_path.unlink(missing_ok=True)
    return extracted


def download_gdelt(days_back: int = 5, max_files: int = 96,
                   workers: int = 8) -> dict:
    """Download GDELT 15-min export files from the last ``days_back`` days.

    Each export covers 15 minutes of global events (~1k rows). Default
    pulls 96 files = a full day of global news activity.
    """
    print(f"[ingest] master list -> filtering last {days_back} days, "
          f"max {max_files} files")
    urls = _fetch_master_list()

    cutoff = (dt.datetime.utcnow() - dt.timedelta(days=days_back)).strftime("%Y%m%d")
    urls = [u for u in urls if u.split("/")[-1][:8] >= cutoff]
    urls = sorted(urls, reverse=True)[:max_files]

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    UNZIPPED_DIR.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_download_one, u, DOWNLOAD_DIR) for u in urls]
        for fut in as_completed(futs):
            res = fut.result()
            if res is not None:
                downloaded.append(res)

    extracted_total = 0
    for zp in downloaded:
        extracted_total += _unzip_one(zp, UNZIPPED_DIR)

    csv_count = sum(1 for _ in UNZIPPED_DIR.glob("*.CSV"))
    bytes_total = sum(p.stat().st_size for p in UNZIPPED_DIR.glob("*.CSV"))
    summary = {
        "urls_targeted": len(urls),
        "downloaded": len(downloaded),
        "newly_extracted": extracted_total,
        "csv_files_total": csv_count,
        "csv_bytes_total": bytes_total,
    }
    print(f"[ingest] done: {summary}")
    return summary


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--days-back", type=int, default=5)
    ap.add_argument("--max-files", type=int, default=96)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    download_gdelt(args.days_back, args.max_files, args.workers)
