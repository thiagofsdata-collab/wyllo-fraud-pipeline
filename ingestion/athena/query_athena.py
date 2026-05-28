"""
Run ad-hoc Athena queries over the cataloged raw data.

PRODUCTION PATH — requires AWS credentials, a Glue catalog populated by
the crawler, and an S3 bucket for Athena results.
Not run in the local-first demo (use DuckDB / Athena-equivalent SQL there).

Athena is the ad-hoc investigation tool: when a fraud analyst asks
"did this merchant have a return spike last week?", this is the path
that answers it without spinning up a warehouse.

Run (with credentials configured):
    python ingestion/athena/query_athena.py --database wyllo_fraud_catalog \\
        --output s3://wyllo-athena-results/
"""

from __future__ import annotations

import argparse
import os
import sys
import time

# Example investigation queries a fraud analyst might run ad-hoc.
EXAMPLE_QUERIES = {
    "cancellation_rate_by_state": """
        SELECT
            c.customer_state,
            COUNT(*) AS total_orders,
            SUM(CASE WHEN o.order_status = 'canceled' THEN 1 ELSE 0 END) AS canceled,
            ROUND(
                100.0 * SUM(CASE WHEN o.order_status = 'canceled' THEN 1 ELSE 0 END)
                / COUNT(*), 2
            ) AS cancel_rate_pct
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        GROUP BY c.customer_state
        ORDER BY cancel_rate_pct DESC
        LIMIT 20;
    """,
    "low_review_on_delivered": """
        SELECT
            COUNT(*) AS delivered_orders,
            SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END) AS low_review,
            ROUND(
                100.0 * SUM(CASE WHEN r.review_score <= 2 THEN 1 ELSE 0 END)
                / COUNT(*), 2
            ) AS inr_proxy_rate_pct
        FROM orders o
        JOIN reviews r ON o.order_id = r.order_id
        WHERE o.order_status = 'delivered';
    """,
}


def run_query(database: str, output: str, query: str) -> int:
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError:
        print("boto3 not installed. Run: pip install boto3")
        return 1

    athena = boto3.client("athena", region_name=os.getenv("AWS_REGION", "us-east-1"))

    try:
        resp = athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": database},
            ResultConfiguration={"OutputLocation": output},
        )
        qid = resp["QueryExecutionId"]
        print(f"Query submitted: {qid}")

        while True:
            status = athena.get_query_execution(QueryExecutionId=qid)
            state = status["QueryExecution"]["Status"]["State"]
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(2)

        if state != "SUCCEEDED":
            reason = status["QueryExecution"]["Status"].get(
                "StateChangeReason", "unknown"
            )
            print(f"Query {state}: {reason}")
            return 1

        results = athena.get_query_results(QueryExecutionId=qid)
        rows = results["ResultSet"]["Rows"]
        for row in rows:
            print(" | ".join(c.get("VarCharValue", "") for c in row["Data"]))
        return 0
    except NoCredentialsError:
        print(
            "No AWS credentials found.\n"
            "This is the production ad-hoc query path. In the local demo, "
            "run the same SQL against DuckDB instead."
        )
        return 1
    except ClientError as e:
        print(f"AWS error: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ad-hoc Athena query")
    parser.add_argument("--database", required=True, help="Glue catalog database")
    parser.add_argument("--output", required=True, help="S3 path for results")
    parser.add_argument(
        "--query",
        choices=list(EXAMPLE_QUERIES.keys()),
        default="cancellation_rate_by_state",
        help="Which example query to run",
    )
    args = parser.parse_args()
    return run_query(args.database, args.output, EXAMPLE_QUERIES[args.query])


if __name__ == "__main__":
    sys.exit(main())
