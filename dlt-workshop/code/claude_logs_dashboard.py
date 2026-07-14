# /// script
# requires-python = ">=3.10"
# ///
"""Claude Code usage dashboard.

Reads the `agent_logs` dlt pipeline (local Claude Code JSONL logs loaded into
DuckDB) and renders an interactive report with marimo + Altair.

Run with:  marimo edit code/claude_logs_dashboard.py
      or:  marimo run  code/claude_logs_dashboard.py

The `message` column is a JSON blob (the pipeline uses max_table_nesting=0), so
nested fields are read with json_extract / json_extract_string using `$.path`
syntax, and `message.content` is unnested for per-tool / per-block stats.
"""

import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import dlt
    import altair as alt
    import pandas as pd

    return alt, dlt, mo, pd


@app.cell
def _(dlt, pd):
    # Attach the existing pipeline; dlt resolves the last-loaded (dev_mode)
    # dataset from pipeline state, so no dataset name needs to be hard-coded.
    pipeline = dlt.attach("agent_logs")

    def run_sql(sql: str) -> "pd.DataFrame":
        """Run SQL against the pipeline's DuckDB dataset -> DataFrame."""
        with pipeline.sql_client() as client:
            with client.execute_query(sql) as cursor:
                columns = [c[0] for c in cursor.description]
                rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=columns)

    return pipeline, run_sql


@app.cell
def _(mo, pipeline):
    mo.md(f"""
    # 🤖 Claude Code Usage Dashboard

    Source: dlt pipeline **`agent_logs`** → dataset `{pipeline.dataset_name}`
    (local Claude Code JSONL logs loaded into DuckDB).
    """)
    return


@app.cell
def _(run_sql):
    # ---- Summary metrics -------------------------------------------------
    summary = run_sql(
        """
        SELECT
            COUNT(*)                                              AS total_events,
            COUNT(DISTINCT session_id)                            AS sessions,
            COUNT(*) FILTER (WHERE message->>'role' = 'assistant') AS assistant_msgs,
            COUNT(*) FILTER (WHERE message->>'role' = 'user')      AS user_msgs,
            MIN(timestamp)                                        AS first_ts,
            MAX(timestamp)                                        AS last_ts
        FROM messages
        """
    ).iloc[0]

    tokens = run_sql(
        """
        SELECT
            COALESCE(SUM(CAST(json_extract_string(message,'$.usage.input_tokens')          AS BIGINT)),0) AS input_tokens,
            COALESCE(SUM(CAST(json_extract_string(message,'$.usage.output_tokens')         AS BIGINT)),0) AS output_tokens,
            COALESCE(SUM(CAST(json_extract_string(message,'$.usage.cache_read_input_tokens')     AS BIGINT)),0) AS cache_read,
            COALESCE(SUM(CAST(json_extract_string(message,'$.usage.cache_creation_input_tokens') AS BIGINT)),0) AS cache_creation
        FROM messages
        """
    ).iloc[0]

    tool_calls = run_sql(
        """
        SELECT COUNT(*) AS n
        FROM messages, UNNEST(CAST(json_extract(message,'$.content') AS JSON[])) AS t(block)
        WHERE json_type(json_extract(message,'$.content')) = 'ARRAY'
          AND json_extract_string(block,'$.type') = 'tool_use'
        """
    ).iloc[0]["n"]
    return summary, tokens, tool_calls


@app.cell
def _(mo, summary, tokens, tool_calls):
    def _fmt(n):
        return f"{int(n):,}"

    mo.vstack(
        [
            mo.md("## 📊 Summary metrics"),
            mo.hstack(
                [
                    mo.stat(_fmt(summary.total_events), label="Total events", bordered=True),
                    mo.stat(_fmt(summary.sessions), label="Sessions", bordered=True),
                    mo.stat(_fmt(summary.assistant_msgs), label="Assistant msgs", bordered=True),
                    mo.stat(_fmt(summary.user_msgs), label="User msgs", bordered=True),
                    mo.stat(_fmt(tool_calls), label="Tool calls", bordered=True),
                ],
                widths="equal",
            ),
            mo.hstack(
                [
                    mo.stat(_fmt(tokens.output_tokens), label="Output tokens", bordered=True),
                    mo.stat(_fmt(tokens.input_tokens), label="Input tokens", bordered=True),
                    mo.stat(_fmt(tokens.cache_read), label="Cache-read tokens", bordered=True),
                    mo.stat(_fmt(tokens.cache_creation), label="Cache-creation tokens", bordered=True),
                ],
                widths="equal",
            ),
        ]
    )
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Activity over time ---------------------------------------------
    activity = run_sql(
        """
        SELECT
            time_bucket(INTERVAL '15 minutes', timestamp) AS bucket,
            CASE
                WHEN message->>'role' = 'assistant' THEN 'assistant'
                WHEN message->>'role' = 'user'      THEN 'user'
                ELSE 'system/other'
            END AS category,
            COUNT(*) AS events
        FROM messages
        WHERE timestamp IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1
        """
    )

    activity_chart = (
        alt.Chart(activity)
        .mark_area(opacity=0.85)
        .encode(
            x=alt.X("bucket:T", title="Time (15-min buckets)"),
            y=alt.Y("events:Q", title="Events", stack=True),
            color=alt.Color("category:N", title="Category"),
            tooltip=["bucket:T", "category:N", "events:Q"],
        )
        .properties(height=300, width="container", title="Activity over time")
    )

    mo.vstack([mo.md("## 🕒 Activity over time"), mo.ui.altair_chart(activity_chart)])
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Message types ---------------------------------------------------
    msg_types = run_sql(
        "SELECT type AS message_type, COUNT(*) AS n FROM messages GROUP BY 1 ORDER BY 2 DESC"
    )

    msg_types_chart = (
        alt.Chart(msg_types)
        .mark_bar()
        .encode(
            x=alt.X("n:Q", title="Count"),
            y=alt.Y("message_type:N", sort="-x", title="Message type"),
            color=alt.Color("message_type:N", legend=None),
            tooltip=["message_type:N", "n:Q"],
        )
        .properties(height=300, width="container", title="Message types")
    )

    mo.vstack([mo.md("## 🗂️ Message types"), mo.ui.altair_chart(msg_types_chart)])
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Models used -----------------------------------------------------
    models = run_sql(
        """
        SELECT message->>'model' AS model, COUNT(*) AS calls
        FROM messages
        WHERE message->>'model' IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
        """
    )

    models_chart = (
        alt.Chart(models)
        .mark_bar()
        .encode(
            x=alt.X("calls:Q", title="Assistant responses"),
            y=alt.Y("model:N", sort="-x", title="Model"),
            color=alt.Color("model:N", legend=None),
            tooltip=["model:N", "calls:Q"],
        )
        .properties(height=200, width="container", title="Models used")
    )

    mo.vstack([mo.md("## 🧠 Models used"), mo.ui.altair_chart(models_chart)])
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Token usage -----------------------------------------------------
    token_mix = run_sql(
        """
        SELECT * FROM (
            SELECT 'input'          AS token_type, COALESCE(SUM(CAST(json_extract_string(message,'$.usage.input_tokens')          AS BIGINT)),0) AS tokens FROM messages
            UNION ALL
            SELECT 'output'         AS token_type, COALESCE(SUM(CAST(json_extract_string(message,'$.usage.output_tokens')         AS BIGINT)),0) FROM messages
            UNION ALL
            SELECT 'cache_read'     AS token_type, COALESCE(SUM(CAST(json_extract_string(message,'$.usage.cache_read_input_tokens')     AS BIGINT)),0) FROM messages
            UNION ALL
            SELECT 'cache_creation' AS token_type, COALESCE(SUM(CAST(json_extract_string(message,'$.usage.cache_creation_input_tokens') AS BIGINT)),0) FROM messages
        ) ORDER BY tokens DESC
        """
    )

    token_mix_chart = (
        alt.Chart(token_mix)
        .mark_bar()
        .encode(
            x=alt.X("tokens:Q", title="Tokens (log scale)", scale=alt.Scale(type="log")),
            y=alt.Y("token_type:N", sort="-x", title="Token type"),
            color=alt.Color("token_type:N", legend=None),
            tooltip=["token_type:N", "tokens:Q"],
        )
        .properties(height=220, width="container", title="Total tokens by type")
    )

    tokens_over_time = run_sql(
        """
        SELECT
            time_bucket(INTERVAL '15 minutes', timestamp) AS bucket,
            SUM(CAST(json_extract_string(message,'$.usage.output_tokens') AS BIGINT)) AS output_tokens
        FROM messages
        WHERE message->>'role' = 'assistant' AND timestamp IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """
    )

    tokens_time_chart = (
        alt.Chart(tokens_over_time)
        .mark_line(point=True)
        .encode(
            x=alt.X("bucket:T", title="Time (15-min buckets)"),
            y=alt.Y("output_tokens:Q", title="Output tokens"),
            tooltip=["bucket:T", "output_tokens:Q"],
        )
        .properties(height=260, width="container", title="Output tokens over time")
    )

    mo.vstack(
        [
            mo.md("## 🎟️ Token usage"),
            mo.ui.altair_chart(token_mix_chart),
            mo.ui.altair_chart(tokens_time_chart),
        ]
    )
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Top projects ----------------------------------------------------
    projects = run_sql(
        """
        SELECT
            list_extract(str_split(replace(cwd, '\\\\', '/'), '/'), -1) AS project,
            COUNT(*) AS events
        FROM messages
        WHERE cwd IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
        LIMIT 15
        """
    )

    projects_chart = (
        alt.Chart(projects)
        .mark_bar()
        .encode(
            x=alt.X("events:Q", title="Events"),
            y=alt.Y("project:N", sort="-x", title="Project (cwd)"),
            color=alt.Color("project:N", legend=None),
            tooltip=["project:N", "events:Q"],
        )
        .properties(height=300, width="container", title="Top projects")
    )

    mo.vstack([mo.md("## 📁 Top projects"), mo.ui.altair_chart(projects_chart)])
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Tool usage ------------------------------------------------------
    tools = run_sql(
        """
        SELECT
            json_extract_string(block,'$.name') AS tool,
            COUNT(*) AS calls
        FROM messages, UNNEST(CAST(json_extract(message,'$.content') AS JSON[])) AS t(block)
        WHERE json_type(json_extract(message,'$.content')) = 'ARRAY'
          AND json_extract_string(block,'$.type') = 'tool_use'
        GROUP BY 1 ORDER BY 2 DESC
        """
    )

    tools_chart = (
        alt.Chart(tools)
        .mark_bar()
        .encode(
            x=alt.X("calls:Q", title="Tool calls"),
            y=alt.Y("tool:N", sort="-x", title="Tool"),
            color=alt.Color("tool:N", legend=None),
            tooltip=["tool:N", "calls:Q"],
        )
        .properties(height=300, width="container", title="Tool usage")
    )

    mo.vstack([mo.md("## 🔧 Tool usage"), mo.ui.altair_chart(tools_chart)])
    return


if __name__ == "__main__":
    app.run()
