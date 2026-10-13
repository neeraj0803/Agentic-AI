import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.worker_api import router as worker_router
from .api.workflow_api import router as workflow_router
from .config import settings
from .telemetry import worker_logger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_logger.info(
        f"QE-201 Agent Worker Orchestrator initialized on port {getattr(settings, 'port', 8002)}. Continuous LangGraph execution window ready."
    )
    yield
    worker_logger.info("Agent Worker service shutting down gracefully.")


app = FastAPI(
    title="QE-201 Agent Worker Orchestrator",
    description="LangGraph-powered worker orchestrator for manual and regression test case drafting with SSE streaming, dynamic checkpoints, and LLM-driven HITL feedback.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(workflow_router)
app.include_router(worker_router)


@app.get("/")
def root():
    return {
        "service": "QE-201 Agent Worker Orchestrator",
        "version": "1.0.0",
        "status": "online",
        "runtime": "LangGraph Continuous Execution Window & Dynamic Workflow Orchestrator",
    }


@app.get("/health")
async def health():
    return {
        "status": "UP",
        "orchestrator": "ok",
        "agent": "QE-201-draft-test-cases-from-jira",
        "version": "1.0.0",
        "framework": "LangGraph + FastAPI SSE",
    }
