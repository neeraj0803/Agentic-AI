from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.agents_api import router as agents_router
from .api.checkpoint_api import router as checkpoint_router
from .api.metrics_api import router as metrics_router
from .api.preflight_api import router as preflight_router
from .api.runs_api import router as runs_router
from .api.sessions_api import router as sessions_router
from .api.stream_api import router as stream_router
from .config import settings
from .storage.orchestrator_storage import OrchestratorStorage
from .telemetry import logger, register_logger_storage_hook, register_tracer_storage_hook


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize storage & register hooks for OpenTelemetry spans and structured logs
    storage = OrchestratorStorage()
    register_tracer_storage_hook(storage)
    register_logger_storage_hook(storage)

    summary = storage.get_database_summary()
    logger.info(
        f"Platform Orchestrator Service starting up on port {settings.port} [v{settings.version}]...",
        database=summary["database_path"],
        tables=summary["table_counts"]
    )
    yield
    logger.info("Platform Orchestrator Service shutting down...")


app = FastAPI(
    title="Platform Orchestrator Service",
    description="Enterprise control plane for AI-DLC / MTech Apex Platform. Manages run lifecycles, durable checkpoints, telemetry persistence, and worker dispatching.",
    version=settings.version,
    lifespan=lifespan
)

# CORS middleware for Web Agent Portal integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount endpoints under /api/orchestrator prefix
app.include_router(sessions_router, prefix="/api/orchestrator")
app.include_router(agents_router, prefix="/api/orchestrator")
app.include_router(preflight_router, prefix="/api/orchestrator")
app.include_router(runs_router, prefix="/api/orchestrator")
app.include_router(checkpoint_router, prefix="/api/orchestrator")
app.include_router(stream_router, prefix="/api/orchestrator")
app.include_router(metrics_router, prefix="/api/orchestrator")



@app.get("/")
def root():
    return {
        "service": "Platform Orchestrator Service",
        "version": settings.version,
        "status": "online",
        "docs_url": "/docs",
        "metrics_url": "/api/orchestrator/metrics",
        "database_url": "/api/orchestrator/telemetry/database"
    }


@app.get("/health")
def health():
    return {"status": "UP", "service": "platform-orchestrator"}
