from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.context_api import router as context_router
from .api.prd_api import router as prd_router
from .api.confluence_api import router as confluence_router
from .api.workflow_api import router as workflow_router
from .api.mcp_api import router as mcp_router

app = FastAPI(
    title="Agentic AI PRD Generation Platform",
    description="End-to-End Agentic PRD Generation Platform with Mock MCP Skill & Context Engines",
    version="2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"status": "ok", "service": "Agentic PRD Generation Platform", "version": "2.0"}


app.include_router(
    context_router,
    prefix="/context",
    tags=["Context Analyzer"]
)

app.include_router(
    confluence_router,
    prefix="/confluence",
    tags=["Confluence Mock"]
)

app.include_router(
    prd_router,
    prefix="/prd",
    tags=["PRD Generator"]
)

app.include_router(
    workflow_router
)

app.include_router(
    mcp_router
)

