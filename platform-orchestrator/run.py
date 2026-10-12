"""
Launcher script for Platform Orchestrator Service.
Usage:
    python run.py
"""
import sys
import uvicorn
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.config import settings

if __name__ == "__main__":
    host = getattr(settings, "host", "0.0.0.0")
    port = getattr(settings, "port", 8001)
    print(f"Starting Platform Orchestrator on http://{host}:{port}")
    print(f"Swagger API Docs: http://localhost:{port}/docs")
    print(f"Observability Metrics: http://localhost:{port}/api/orchestrator/metrics")
    print(f"Database Telemetry: http://localhost:{port}/api/orchestrator/telemetry/database")
    uvicorn.run("src.main:app", host=host, port=port, reload=True)
