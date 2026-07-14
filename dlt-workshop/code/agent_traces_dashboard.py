# /// script
# requires-python = ">=3.10"
# ///
"""Agent Traces dashboard.

Reads the `agent_traces_api` dlt pipeline (Claude Code Agent Logs REST API,
loaded into DuckDB by code/rest_api_pipeline.py) and renders an interactive
report with marimo + Altair.

Run with:  marimo edit code/agent_traces_dashboard.py
      or:  marimo run  code/agent_traces_dashboard.py

Unlike the JSONL dashboard, this pipeline stores fully-normalized tables:
  - `logs`                    : one row per log event (typed columns)
  - `logs__message__content`  : one row per assistant content block
                                (type='text' | 'tool_use', with tool `name`)
so nested JSON parsing is not needed -- tool usage comes straight from the
child table joined on `_dlt_parent_id = logs._dlt_id`.
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
    # Attach the existing pipeline; dlt resolves the last-loaded dataset from
    # pipeline state, so the dataset name does not need to be hard-coded.
    pipeline = dlt.attach("agent_traces_api")

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
    # 🛰️ Agent Traces Dashboard

    Source: dlt pipeline **`agent_traces_api`** → dataset `{pipeline.dataset_name}`
    (Claude Code Agent Logs REST API loaded into DuckDB).
    """)
    return


@app.cell
def _(run_sql):
    # ---- Summary metrics -------------------------------------------------
    summary = run_sql(
        """
        SELECT
            COUNT(*)                                       AS total_logs,
            COUNT(DISTINCT session_id)                     AS sessions,
            COUNT(*) FILTER (WHERE type = 'assistant')     AS assistant_msgs,
            COUNT(*) FILTER (WHERE type = 'user')          AS user_msgs,
            COUNT(DISTINCT message__model)                 AS models,
            COUNT(DISTINCT cwd)                            AS projects,
            COALESCE(SUM(usage__input_tokens), 0)          AS input_tokens,
            COALESCE(SUM(usage__output_tokens), 0)         AS output_tokens,
            MIN(timestamp)                                 AS first_ts,
            MAX(timestamp)                                 AS last_ts
        FROM logs
        """
    ).iloc[0]

    tool_calls = run_sql(
        """
        SELECT COUNT(*) AS n
        FROM logs__message__content
        WHERE type = 'tool_use'
        """
    ).iloc[0]["n"]
    return summary, tool_calls


@app.cell
def _(mo, summary, tool_calls):
    def _fmt(n):
        return f"{int(n):,}"

    mo.vstack(
        [
            mo.md("## 📊 Summary KPIs"),
            mo.hstack(
                [
                    mo.stat(_fmt(summary.total_logs), label="Total logs", bordered=True),
                    mo.stat(_fmt(summary.sessions), label="Sessions", bordered=True),
                    mo.stat(_fmt(summary.assistant_msgs), label="Assistant msgs", bordered=True),
                    mo.stat(_fmt(summary.user_msgs), label="User msgs", bordered=True),
                    mo.stat(_fmt(tool_calls), label="Tool calls", bordered=True),
                ],
                widths="equal",
            ),
            mo.hstack(
                [
                    mo.stat(_fmt(summary.models), label="Models", bordered=True),
                    mo.stat(_fmt(summary.projects), label="Projects", bordered=True),
                    mo.stat(_fmt(summary.input_tokens), label="Input tokens", bordered=True),
                    mo.stat(_fmt(summary.output_tokens), label="Output tokens", bordered=True),
                ],
                widths="equal",
            ),
            mo.md(f"*Time range: {summary.first_ts} → {summary.last_ts}*"),
        ]
    )
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Activity over time ---------------------------------------------
    activity = run_sql(
        """
        SELECT
            time_bucket(INTERVAL '1 hour', timestamp) AS bucket,
            type                                      AS category,
            COUNT(*)                                  AS events
        FROM logs
        WHERE timestamp IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1
        """
    )

    activity_chart = (
        alt.Chart(activity)
        .mark_area(opacity=0.85)
        .encode(
            x=alt.X("bucket:T", title="Time (hourly buckets)"),
            y=alt.Y("events:Q", title="Events", stack=True),
            color=alt.Color("category:N", title="Type"),
            tooltip=["bucket:T", "category:N", "events:Q"],
        )
        .properties(height=300, width="container", title="Activity over time")
    )

    mo.vstack([mo.md("## 🕒 Activity over time"), mo.ui.altair_chart(activity_chart)])
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Logs by type ----------------------------------------------------
    log_types = run_sql(
        "SELECT type AS log_type, COUNT(*) AS n FROM logs GROUP BY 1 ORDER BY 2 DESC"
    )

    log_types_chart = (
        alt.Chart(log_types)
        .mark_bar()
        .encode(
            x=alt.X("n:Q", title="Count"),
            y=alt.Y("log_type:N", sort="-x", title="Log type"),
            color=alt.Color("log_type:N", legend=None),
            tooltip=["log_type:N", "n:Q"],
        )
        .properties(height=200, width="container", title="Logs by type")
    )

    mo.vstack([mo.md("## 🗂️ Logs by type"), mo.ui.altair_chart(log_types_chart)])
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Model usage -----------------------------------------------------
    models = run_sql(
        """
        SELECT
            message__model                          AS model,
            COUNT(*)                                AS calls,
            COALESCE(SUM(usage__output_tokens), 0)  AS output_tokens
        FROM logs
        WHERE message__model IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
        """
    )

    model_calls_chart = (
        alt.Chart(models)
        .mark_bar()
        .encode(
            x=alt.X("calls:Q", title="Assistant responses"),
            y=alt.Y("model:N", sort="-x", title="Model"),
            color=alt.Color("model:N", legend=None),
            tooltip=["model:N", "calls:Q", "output_tokens:Q"],
        )
        .properties(height=220, width="container", title="Model usage (responses)")
    )

    model_tokens_chart = (
        alt.Chart(models)
        .mark_bar()
        .encode(
            x=alt.X("output_tokens:Q", title="Output tokens"),
            y=alt.Y("model:N", sort="-x", title="Model"),
            color=alt.Color("model:N", legend=None),
            tooltip=["model:N", "output_tokens:Q", "calls:Q"],
        )
        .properties(height=220, width="container", title="Output tokens by model")
    )

    mo.vstack(
        [
            mo.md("## 🧠 Model usage"),
            mo.ui.altair_chart(model_calls_chart),
            mo.ui.altair_chart(model_tokens_chart),
        ]
    )
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Input & output token usage -------------------------------------
    token_mix = run_sql(
        """
        SELECT 'input' AS token_type,  COALESCE(SUM(usage__input_tokens), 0)  AS tokens FROM logs
        UNION ALL
        SELECT 'output' AS token_type, COALESCE(SUM(usage__output_tokens), 0) AS tokens FROM logs
        ORDER BY tokens DESC
        """
    )

    token_mix_chart = (
        alt.Chart(token_mix)
        .mark_bar()
        .encode(
            x=alt.X("tokens:Q", title="Tokens"),
            y=alt.Y("token_type:N", sort="-x", title="Token type"),
            color=alt.Color("token_type:N", legend=None),
            tooltip=["token_type:N", "tokens:Q"],
        )
        .properties(height=160, width="container", title="Total tokens: input vs output")
    )

    tokens_over_time = run_sql(
        """
        SELECT
            time_bucket(INTERVAL '1 hour', timestamp)       AS bucket,
            COALESCE(SUM(usage__input_tokens), 0)           AS input_tokens,
            COALESCE(SUM(usage__output_tokens), 0)          AS output_tokens
        FROM logs
        WHERE type = 'assistant' AND timestamp IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """
    )

    # Long-form for a two-series line chart.
    tokens_long = tokens_over_time.melt(
        id_vars="bucket",
        value_vars=["input_tokens", "output_tokens"],
        var_name="token_type",
        value_name="tokens",
    )

    tokens_time_chart = (
        alt.Chart(tokens_long)
        .mark_line(point=True)
        .encode(
            x=alt.X("bucket:T", title="Time (hourly buckets)"),
            y=alt.Y("tokens:Q", title="Tokens"),
            color=alt.Color("token_type:N", title="Token type"),
            tooltip=["bucket:T", "token_type:N", "tokens:Q"],
        )
        .properties(height=280, width="container", title="Token usage over time")
    )

    mo.vstack(
        [
            mo.md("## 🎟️ Input & output token usage"),
            mo.ui.altair_chart(token_mix_chart),
            mo.ui.altair_chart(tokens_time_chart),
        ]
    )
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Projects & branches --------------------------------------------
    # Derive a short project name from the last path segment of cwd.
    projects = run_sql(
        """
        SELECT
            list_extract(str_split(replace(cwd, '\\\\', '/'), '/'), -1) AS project,
            COUNT(*) AS events
        FROM logs
        WHERE cwd IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
        LIMIT 20
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
        .properties(height=320, width="container", title="Activity by project")
    )

    branches = run_sql(
        """
        SELECT git_branch AS branch, COUNT(*) AS events
        FROM logs
        WHERE git_branch IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
        LIMIT 20
        """
    )

    branches_chart = (
        alt.Chart(branches)
        .mark_bar()
        .encode(
            x=alt.X("events:Q", title="Events"),
            y=alt.Y("branch:N", sort="-x", title="Git branch"),
            color=alt.Color("branch:N", legend=None),
            tooltip=["branch:N", "events:Q"],
        )
        .properties(height=260, width="container", title="Activity by git branch")
    )

    mo.vstack(
        [
            mo.md("## 📁 Projects & branches"),
            mo.ui.altair_chart(projects_chart),
            mo.ui.altair_chart(branches_chart),
        ]
    )
    return


@app.cell
def _(alt, mo, run_sql):
    # ---- Tool & skill usage ---------------------------------------------
    # Assistant content blocks live in the child table; tool_use blocks carry
    # the tool/skill `name`. This dataset contains standard tools only (no
    # separate skill entries), so the panel renders whatever names are present.
    tools = run_sql(
        """
        SELECT name AS tool, COUNT(*) AS calls
        FROM logs__message__content
        WHERE type = 'tool_use' AND name IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
        """
    )

    if tools.empty:
        tools_view = mo.md("_No tool or skill usage found in the loaded data._")
    else:
        tools_chart = (
            alt.Chart(tools)
            .mark_bar()
            .encode(
                x=alt.X("calls:Q", title="Invocations"),
                y=alt.Y("tool:N", sort="-x", title="Tool / skill"),
                color=alt.Color("tool:N", legend=None),
                tooltip=["tool:N", "calls:Q"],
            )
            .properties(height=320, width="container", title="Tool & skill usage")
        )
        tools_view = mo.ui.altair_chart(tools_chart)

    mo.vstack([mo.md("## 🔧 Tool & skill usage"), tools_view])
    return


if __name__ == "__main__":
    app.run()
