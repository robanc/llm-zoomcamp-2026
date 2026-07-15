import duckdb

con = duckdb.connect(".dlt/data/dev/logfire_pipeline.duckdb")

count = con.execute("""
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'agent_traces'
""").fetchone()[0]

print(f"Table count: {count}")

print("\nTables:")
tables = con.execute("""
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'agent_traces'
ORDER BY table_name
""").fetchall()

for table in tables:
    print(table[0])