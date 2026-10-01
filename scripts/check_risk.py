import duckdb

con = duckdb.connect("data/db/abhedya.duckdb", read_only=True)
print("=== MULE RISK LAYER BREAKDOWN ===")
print(con.execute("SELECT layer, count(*), avg(risk_score), max(risk_score) FROM mule_risk GROUP BY layer").fetchdf())

print("\n=== TOP RISK SCORES ===")
print(con.execute("SELECT account_str, risk_score, layer FROM mule_risk ORDER BY risk_score DESC LIMIT 10").fetchdf())

print("\n=== SAMPLE TXNS WITH HIGH RISK RECEIVERS ===")
print(con.execute("""
    SELECT t.sender_acc, t.receiver_acc, t.amount, m.risk_score, m.layer 
    FROM txn t 
    JOIN mule_risk m ON t.receiver_acc = m.account_str 
    ORDER BY m.risk_score DESC LIMIT 10
""").fetchdf())
