"""dlt pipeline: load local Claude agent logs (raw JSONL) into DuckDB.

Source : C:\\Users\\roban\\.claude\\projects\\**\\*.jsonl
Reader : dlt.sources.filesystem filesystem() | read_jsonl()
Target : DuckDB, dataset "agent_logs", table "messages"
"""

import dlt
from dlt.sources.filesystem import filesystem, read_jsonl

# Root folder holding all Claude project logs, as a file:// bucket URL.
BUCKET_URL = "file:///C:/Users/roban/.claude/projects"


def agent_log_messages():
    """filesystem items -> parsed JSONL records, exposed as resource `messages`."""
    files = filesystem(bucket_url=BUCKET_URL, file_glob="**/*.jsonl")
    reader = (files | read_jsonl()).with_name("messages")
    reader.apply_hints(write_disposition="replace")
    return reader


def main():
    pipeline = dlt.pipeline(
        pipeline_name="agent_logs",
        destination="duckdb",
        dataset_name="agent_logs",
        dev_mode=True,
    )

    load_info = pipeline.run(agent_log_messages())
    print(load_info)

    # Report row count in the top-level `messages` table.
    with pipeline.sql_client() as client:
        with client.execute_query("SELECT COUNT(*) FROM messages") as cursor:
            count = cursor.fetchone()[0]
    print(f"\nmessages table row count: {count}")


if __name__ == "__main__":
    main()
