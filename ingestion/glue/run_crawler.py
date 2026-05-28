"""
Trigger an AWS Glue crawler to catalog the raw S3 data into the Glue
Data Catalog, making it queryable from Athena.

PRODUCTION PATH — requires AWS credentials and a pre-created crawler.
Not run in the local-first demo.

The crawler scans s3://{bucket}/raw/ and infers table schemas, registering
them under a Glue database. Once cataloged, Athena can query the raw data
with standard SQL without any ETL.

Run (with credentials configured):
    python ingestion/glue/run_crawler.py --crawler wyllo-raw-crawler
"""

from __future__ import annotations

import argparse
import os
import sys
import time


def run_crawler(crawler_name: str, wait: bool = True) -> int:
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        print("boto3 not installed. Run: pip install boto3")
        return 1

    glue = boto3.client("glue", region_name=os.getenv("AWS_REGION", "us-east-1"))

    try:
        print(f"Starting crawler: {crawler_name}")
        glue.start_crawler(Name=crawler_name)

        if not wait:
            print("Crawler started (not waiting for completion).")
            return 0

        print("Waiting for crawler to finish...")
        while True:
            resp = glue.get_crawler(Name=crawler_name)
            state = resp["Crawler"]["State"]
            print(f"  state={state}")
            if state == "READY":
                break
            time.sleep(15)

        metrics = glue.get_crawler_metrics(CrawlerNameList=[crawler_name])
        m = metrics["CrawlerMetricsList"][0]
        print(
            f"Done. Tables created: {m.get('TablesCreated', 0)}, "
            f"updated: {m.get('TablesUpdated', 0)}"
        )
        return 0
    except NoCredentialsError:
        print(
            "No AWS credentials found.\n"
            "This is the production cataloging path. The local demo skips "
            "Glue entirely — DuckDB reads the raw files directly."
        )
        return 1
    except ClientError as e:
        if e.response["Error"]["Code"] == "EntityNotFoundException":
            print(
                f"Crawler '{crawler_name}' not found. Create it first "
                "(Terraform/CDK/console) pointing at s3://your-bucket/raw/"
            )
        else:
            print(f"AWS error: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AWS Glue crawler")
    parser.add_argument("--crawler", required=True, help="Glue crawler name")
    parser.add_argument(
        "--no-wait", action="store_true", help="Don't wait for completion"
    )
    args = parser.parse_args()
    return run_crawler(args.crawler, wait=not args.no_wait)


if __name__ == "__main__":
    sys.exit(main())
