"""dlt REST API pipeline for the Claude Code Agent Logs API.

Source docs: https://test-agent-traces-api-xt2e7ottma-ew.a.run.app/docs

The /logs endpoint serves 1,000,000 fake Claude Code agent logs in chunks,
using offset/limit pagination. The response envelope looks like:

    {"total": 1000000, "offset": 0, "limit": 1000, "count": 1000,
     "next_offset": 1000, "logs": [ {...}, ... ]}

We use dlt's REST API source with an "offset" paginator that reads the grand
total from the response's `total` field, and select the `logs` array via
`data_selector="logs"`. `index` is the primary key.

Modes (safety caps so we never accidentally pull all 1M rows):
    sample -> one page of 1,000 records
    capped -> no more than 20,000 records (default)
    full   -> all 1,000,000 records (only when explicitly requested)

Usage:
    uv run python code/rest_api_pipeline.py sample
    uv run python code/rest_api_pipeline.py capped
    uv run python code/rest_api_pipeline.py full     # explicit opt-in only
"""

import sys

import dlt
from dlt.hub import run as hub_run  # aliased so it doesn't shadow this module's run()
from dlt.sources.rest_api import rest_api_source

BASE_URL = "https://test-agent-traces-api-xt2e7ottma-ew.a.run.app"

PAGE_LIMIT = 1000  # API max rows per request

# Per-mode cap on the offset. The offset paginator stops once the next offset
# would reach maximum_offset, so the number of rows loaded is maximum_offset.
MODE_MAX_OFFSET = {
    "sample": 1_000,     # one page of 1,000 records
    "capped": 20_000,    # no more than 20,000 records
    "full": None,        # no cap -> all 1,000,000 records
}


def build_source(mode: str):
    """Build the REST API source for the /logs endpoint in the given mode."""
    maximum_offset = MODE_MAX_OFFSET[mode]

    return rest_api_source(
        {
            "client": {
                "base_url": BASE_URL,
                "paginator": {
                    "type": "offset",
                    "limit": PAGE_LIMIT,
                    "offset": 0,
                    "limit_param": "limit",
                    "offset_param": "offset",
                    "total_path": "total",       # read grand total from response
                    "maximum_offset": maximum_offset,
                    "stop_after_empty_page": True,
                },
            },
            "resources": [
                {
                    "name": "logs",
                    "endpoint": {
                        "path": "/logs",
                        "data_selector": "logs",
                    },
                    "primary_key": "index",
                    "write_disposition": "replace",
                }
            ],
        }
    )


def run(mode: str = "capped"):
    if mode not in MODE_MAX_OFFSET:
        raise SystemExit(
            f"Unknown mode {mode!r}. Choose one of: {', '.join(MODE_MAX_OFFSET)}"
        )

    pipeline = dlt.pipeline(
        pipeline_name="agent_traces_api",
        destination="playground",
        dataset_name="agent_traces",
    )

    print(f"Running mode={mode} (max_offset={MODE_MAX_OFFSET[mode]}) ...")
    info = pipeline.run(build_source(mode))
    print(info)
    return pipeline, info


@hub_run.pipeline("agent_traces_api")
def ingest_agent_traces():
    """Deployed job: load /logs in capped (20,000-record) mode into Playground."""
    run("capped")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "capped"
    run(mode)
