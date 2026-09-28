from fastapi import APIRouter, HTTPException
from typing import Any, Dict
from ..mcp import MockSkillEngine, MockContextEngine

router = APIRouter(prefix="/api/mcp", tags=["MCP Mock Engines"])

skill_engine = MockSkillEngine()
context_engine = MockContextEngine()


@router.post("/rpc")
async def execute_mcp_rpc(payload: Dict[str, Any]):
    """
    Direct JSON-RPC 2.0 endpoint for MCP Mock Engines.
    Routes `discover_skills` to MockSkillEngine and `prism.context.retrieve` to MockContextEngine.
    """
    method = payload.get("method", "")
    params = payload.get("params", {})
    tool_name = params.get("name", "")

    if tool_name == "discover_skills":
        return skill_engine.handle_request(payload)
    elif tool_name == "prism.context.retrieve":
        return context_engine.handle_request(payload)
    else:
        if "skill" in tool_name or "discover" in tool_name:
            return skill_engine.handle_request(payload)
        return context_engine.handle_request(payload)


@router.get("/skills/catalog")
async def get_skills_catalog():
    """
    Returns all registered mock skills in the catalog.
    """
    return {"skills": skill_engine._skills_catalog}

