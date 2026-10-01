FROM python:3.12-slim

WORKDIR /app

# Install system packages required for WeasyPrint & Pango PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libharfbuzz0b \
    pango1.0-tools \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY configs ./configs
COPY scripts ./scripts
COPY data ./data

EXPOSE 8000

ENV PYTHONPATH=.
ENV ABHEDYA_DB_PATH=data/db/abhedya.duckdb

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
