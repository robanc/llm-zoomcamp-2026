import duckdb

con = duckdb.connect(".dlt/data/dev/logfire_pipeline.duckdb")

rows = con.execute("""
SELECT
    trace_id,
    span_name,
    attributes__gen_ai_usage_input_tokens AS input_tokens,
    start_timestamp
FROM agent_traces.records
WHERE attributes__gen_ai_usage_input_tokens IS NOT NULL
ORDER BY start_timestamp
""").fetchall()

for row in rows:
    print(row)