.PHONY: setup generate ingest detect run test eval benchmark clean docker-build docker-up

PYTHON = python
PYTEST = pytest

setup:
	$(PYTHON) -m pip install -r requirements.txt
	npm --prefix frontend install

generate:
	$(PYTHON) scripts/generate_synthetic.py --rows 2000000 --accounts 25000 --mules 1500 --seed 42 --out data/raw/transactions.csv

ingest:
	$(PYTHON) -m backend.core.ingest --csv data/raw/transactions.csv --db data/db/abhedya.duckdb

detect:
	$(PYTHON) scripts/run_detection.py --db data/db/abhedya.duckdb --config configs/scoring.yaml

run:
	$(PYTHON) -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 &
	npm --prefix frontend run dev

test:
	$(PYTEST) backend/tests/

eval:
	$(PYTHON) scripts/evaluate.py --db data/db/abhedya.duckdb

benchmark:
	$(PYTHON) scripts/benchmark.py data/db/abhedya.duckdb

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

clean:
	rm -rf data/parquet/* data/db/* __pycache__ .pytest_cache frontend/node_modules frontend/dist
