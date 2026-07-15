from datetime import UTC, datetime, timedelta
import os

import dlt
import requests
from dotenv import load_dotenv


load_dotenv()

LOGFIRE_URL = "https://logfire-us.pydantic.dev/v2/query"


def fetch_logfire_traces() -> list[dict]:
    """Download recent Logfire records using the Logfire Query API."""
    read_token = os.getenv("LOGFIRE_READ_TOKEN")

    if not read_token:
        raise RuntimeError("LOGFIRE_READ_TOKEN is missing from .env")

    # Fetch enough history to include the homework agent runs.
    min_timestamp = datetime.now(tz=UTC) - timedelta(days=7)

    sql = """
    SELECT *
    FROM records
    ORDER BY start_timestamp
    """

    response = requests.post(
        LOGFIRE_URL,
        headers={
            "Authorization": f"Bearer {read_token}",
            "Accept": "application/json",
        },
        json={
            "sql": sql,
            "min_timestamp": min_timestamp.isoformat(),
            "limit": 10000,
        },
        timeout=60,
    )

    response.raise_for_status()

    payload = response.json()
    rows = payload.get("data", [])

    print(f"Downloaded {len(rows)} Logfire records")
    return rows


def main() -> None:
    traces = fetch_logfire_traces()

    if not traces:
        raise RuntimeError(
            "No Logfire records were returned. Run main.py again and retry."
        )

    pipeline = dlt.pipeline(
        pipeline_name="logfire_pipeline",
        destination="duckdb",
        dataset_name="agent_traces",
    )

    load_info = pipeline.run(
        traces,
        table_name="records",
        write_disposition="replace",
    )

    print(load_info)
    print(f"DuckDB location: {pipeline.pipeline_name}.duckdb")


if __name__ == "__main__":
    main()