"""
Launcher script for Agent Worker Service.
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
    port = getattr(settings, "port", 8002)
    print(f"Starting Agent Worker on http://{host}:{port}")
    print(f"Swagger API Docs: http://localhost:{port}/docs")
    uvicorn.run("src.main:app", host=host, port=port, reload=True)
