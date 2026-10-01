@echo off
echo === Starting Abhedya-Chakra Cyber-Crime Engine (100%% Offline Air-Gapped Mode) ===

if not exist "data\db\abhedya.duckdb" (
    echo [1/3] Generating synthetic transaction dataset...
    python scripts\generate_synthetic.py --rows 2000000 --accounts 25000 --mules 1500 --seed 42 --out data\raw\transactions.csv

    echo [2/3] Ingesting CSV into persistent DuckDB database...
    python -m backend.core.ingest --csv data\raw\transactions.csv

    echo [3/3] Executing Mule Detection & Risk Scoring pipeline...
    python scripts\run_detection.py --db data\db\abhedya.duckdb
)

if not exist "frontend\dist\index.html" (
    echo Building static offline frontend...
    cd frontend
    call npm run build
    cd ..
)

echo.
echo =========================================================================
echo  Abhedya-Chakra is running offline at: http://localhost:8000
echo =========================================================================
echo.

python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
