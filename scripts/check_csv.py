import duckdb

con = duckdb.connect("data/db/abhedya.duckdb", read_only=True)
print("=== INGEST REPORT ===")
report = con.execute("SELECT category, dropped_count, details FROM ingest_report").fetchdf()
for _, row in report.iterrows():
    print(f"Category: {row['category']} | Dropped Count: {row['dropped_count']} | Details: {row['details']}")

print("\n=== RAW TXNS SAMPLE ===")
df = con.execute("SELECT * FROM raw_txns LIMIT 5").fetchdf()
print(df.to_string())


