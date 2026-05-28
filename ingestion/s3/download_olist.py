"""
Download the Olist Brazilian E-Commerce dataset from Kaggle.

Two options:
  1. Kaggle CLI (recommended) — requires `kaggle.json` in ~/.kaggle/
     Set up: https://github.com/Kaggle/kaggle-api#api-credentials
  2. Manual download — instructions printed if CLI is not configured.

Output: 9 CSV files in ./data/raw/

Run from project root:
    python ingestion/s3/download_olist.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

DATASET = "olistbr/brazilian-ecommerce"
TARGET_DIR = Path("data/raw")

EXPECTED_FILES = [
    "olist_customers_dataset.csv",
    "olist_geolocation_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "olist_orders_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "product_category_name_translation.csv",
]


def check_kaggle_cli() -> bool:
    """Check whether the kaggle CLI is installed and configured."""
    if shutil.which("kaggle") is None:
        return False
    try:
        result = subprocess.run(
            ["kaggle", "datasets", "list", "--max-size", "1"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def download_via_cli() -> None:
    """Download and unzip the dataset via Kaggle CLI."""
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DATASET} into {TARGET_DIR}/ ...")
    subprocess.run(
        [
            "kaggle",
            "datasets",
            "download",
            "-d",
            DATASET,
            "-p",
            str(TARGET_DIR),
            "--unzip",
        ],
        check=True,
    )
    print("Download complete.")


def verify_files() -> tuple[list[str], list[str]]:
    """Return (present, missing) file lists."""
    present, missing = [], []
    for fname in EXPECTED_FILES:
        if (TARGET_DIR / fname).exists():
            present.append(fname)
        else:
            missing.append(fname)
    return present, missing


def print_manual_instructions() -> None:
    print(
        "\n"
        "Kaggle CLI is not installed or not configured.\n\n"
        "OPTION A — install and configure Kaggle CLI (recommended)\n"
        "  pip install kaggle\n"
        "  # then place your API token at ~/.kaggle/kaggle.json\n"
        "  # token from: https://www.kaggle.com/settings -> API -> Create new token\n"
        "  chmod 600 ~/.kaggle/kaggle.json\n"
        "  python ingestion/s3/download_olist.py  # re-run\n\n"
        "OPTION B — manual download\n"
        "  1. Go to: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce\n"
        "  2. Click 'Download' (login required)\n"
        "  3. Unzip into ./data/raw/\n"
        "  4. Run: python ingestion/s3/download_olist.py  # to verify\n"
    )


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    present, missing = verify_files()
    if not missing:
        print(f"All {len(EXPECTED_FILES)} Olist CSVs already present in {TARGET_DIR}/")
        for f in present:
            size_mb = (TARGET_DIR / f).stat().st_size / 1_000_000
            print(f"  {f}  ({size_mb:.1f} MB)")
        return 0

    if not check_kaggle_cli():
        print(f"Missing files: {len(missing)} of {len(EXPECTED_FILES)}")
        print_manual_instructions()
        return 1

    download_via_cli()

    present, missing = verify_files()
    if missing:
        print(f"WARNING: {len(missing)} expected files still missing after download:")
        for f in missing:
            print(f"  - {f}")
        return 1

    print(f"\nVerified {len(present)} files in {TARGET_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
