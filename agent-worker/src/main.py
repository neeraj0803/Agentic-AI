from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.worker_api import router as worker_router
from .config import settings
from .telemetry import worker_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_logger.info(
        f"Agent Worker service initialized on port {getattr(settings, 'port', 8002)}. Continuous LangGraph execution window ready."
    )
    yield
    worker_logger.info("Agent Worker service shutting down gracefully.")


app = FastAPI(
    title="Agent Worker Service",
    description="Agent Worker runtime executing continuous LangGraph workflows with durable checkpoints.",
    version=settings.version,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(worker_router)


@app.get("/")
def root():
    return {
        "service": "Agent Worker Service",
        "version": settings.version,
        "status": "online",
        "runtime": "LangGraph Continuous Execution Window"
    }
