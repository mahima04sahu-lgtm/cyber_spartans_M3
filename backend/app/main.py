"""
Abhedya-Chakra FastAPI Application Entry Point.
"""

from contextlib import asynccontextmanager
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.db import init_db, close_db, get_db
from backend.app.schemas import HealthResponse
from backend.app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle context manager: Initialize database connection on startup and clean up on shutdown."""
    print("Starting Abhedya-Chakra API server...")
    try:
        con = init_db()
        print("DuckDB Connection initialized successfully.")
        from backend.core.trace import get_graph
        get_graph(con)
    except Exception as e:
        print(f"Warning: Database initialization deferred or failed: {e}")
    yield
    print("Shutting down Abhedya-Chakra API server...")
    close_db()


app = FastAPI(
    title="Abhedya-Chakra API",
    description="Cyber-Crime Money Mule Detection & Tracing Core API Engine",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for localhost development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Middleware logging response time and setting X-Process-Time header."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


@app.get("/")
def root():
    """Root endpoint welcoming user and linking to docs."""
    return {
        "title": "Abhedya-Chakra Cyber-Crime Money Mule Detection API",
        "status": "online",
        "documentation": "/docs",
        "health_check": "/health"
    }


@app.get("/health", response_model=HealthResponse)
def health_check():
    """System health check endpoint."""
    db_connected = False
    try:
        con = get_db()
        row = con.execute("SELECT 1").fetchone()
        db_connected = row is not None and row[0] == 1
    except Exception:
        db_connected = False
        
    return HealthResponse(
        status="ok" if db_connected else "degraded",
        db_connected=db_connected,
    )


# Include API router
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
