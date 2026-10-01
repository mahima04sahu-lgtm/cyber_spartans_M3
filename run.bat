@echo off
echo === Starting Abhedya-Chakra Cyber-Crime Engine ===

if not exist "data\db\abhedya.duckdb" (
    echo [1/4] Generating 2,000,000 synthetic transaction dataset...
    python scripts\generate_synthetic.py --rows 2000000 --accounts 25000 --mules 1500 --seed 42 --out data\raw\transactions.csv

    echo [2/4] Ingesting CSV into persistent DuckDB ART indexes...
    python -m backend.core.ingest --csv data\raw\transactions.csv

    echo [3/4] Executing Mule Detection & Risk Scoring pipeline...
    python scripts\run_detection.py --db data\db\abhedya.duckdb
)

echo [4/4] Launching FastAPI Backend & Vite Frontend...
start cmd /k "python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload"
cd frontend
npm run dev
