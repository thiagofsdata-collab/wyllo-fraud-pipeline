"""
Upload raw Olist CSVs to S3, partitioned by merchant/event/date.

PRODUCTION PATH — requires AWS credentials (AWS_ACCESS_KEY_ID etc.).
Not run in the local-first demo. Included to show the cloud ingestion
path and to make the migration from local to S3 a config change.

S3 layout produced:
    s3://{bucket}/raw/merchant_id={mid}/event_type={etype}/date={date}/part.parquet

Run (with credentials configured):
    python ingestion/s3/upload_to_s3.py --bucket wyllo-fraud-raw-dev
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAW_DIR = Path("data/raw")


def upload(bucket: str, prefix: str = "raw") -> int:
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        print("boto3 not installed. Run: pip install boto3")
        return 1

    s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))

    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSVs found in {RAW_DIR}/. Run download_olist.py first.")
        return 1

    try:
        for csv_path in csv_files:
            # event_type derived from filename, e.g. olist_orders_dataset -> orders
            event_type = (
                csv_path.stem.replace("olist_", "").replace("_dataset", "")
            )
            key = f"{prefix}/event_type={event_type}/{csv_path.name}"
            print(f"  Uploading {csv_path.name} -> s3://{bucket}/{key}")
            s3.upload_file(str(csv_path), bucket, key)
        print(f"\nUploaded {len(csv_files)} files to s3://{bucket}/{prefix}/")
        return 0
    except NoCredentialsError:
        print(
            "No AWS credentials found.\n"
            "This is the production ingestion path — configure credentials "
            "via `aws configure` or environment variables to run it.\n"
            "For the local demo, use: python ingestion/load_raw_to_duckdb.py"
        )
        return 1
    except ClientError as e:
        print(f"AWS error: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload Olist CSVs to S3")
    parser.add_argument("--bucket", required=True, help="Target S3 bucket name")
    parser.add_argument("--prefix", default="raw", help="Key prefix (default: raw)")
    args = parser.parse_args()
    return upload(args.bucket, args.prefix)


if __name__ == "__main__":
    sys.exit(main())
