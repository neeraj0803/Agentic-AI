from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from ..models.run_models import (
    ResolveIntentRequest,
    ResolveIntentResponse
)
from ..services.intent_resolver import intent_resolver
from ..services.mock_context_engine import mock_context_engine
from ..services.mock_skills_engine import mock_skills_engine
from ..services.workflow_registry import workflow_registry

router = APIRouter(prefix="/agents", tags=["Agent Catalog & Workflow Discovery"])


@router.get("", response_model=List[Dict[str, Any]])
async def list_agent_workflows():
    """
    Lists all registered enterprise agent workflows (AG-101 through AG-501)
    loaded dynamically from YAML definitions.
    """
    return workflow_registry.list_workflows()


@router.get("/{agent_id}", response_model=Dict[str, Any])
async def get_agent_workflow(agent_id: str):
    """
    Retrieves full workflow specification, metadata, schema requirements,
    and step descriptions for a specific agent workflow.
    """
    wf = workflow_registry.get_workflow(agent_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Agent workflow '{agent_id}' not found.")
    return wf


@router.post(":resolve-intent", response_model=ResolveIntentResponse)
async def resolve_agent_intent(req: ResolveIntentRequest):
    """
    Analyzes user text prompt and scores matching against published workflow catalog.
    Returns top matched agent ID, confidence score, and extracted parameters.
    """
    res = intent_resolver.resolve_intent(
        user_prompt=req.user_prompt,
        team_id=req.team_id,
        context_hints=req.context_hints
    )
    return res


@router.get("/{agent_id}/context-and-skills")
async def get_agent_context_and_skills(
    agent_id: str,
    team_id: str = Query("team-checkout-qe", description="Team workspace ID"),
    application_name: str = Query("Checkout Service", description="Application name")
):
    """
    Previews resolved Context Pack capabilities and dynamic Skill MCP bindings
    for the specified workflow.
    """
    wf = workflow_registry.get_workflow(agent_id)
    if not wf:
        raise HTTPException(status_code=404, detail=f"Agent workflow '{agent_id}' not found.")

    required_ctx = workflow_registry.extract_required_context(agent_id)
    shortlist_skills = workflow_registry.extract_skill_shortlist(agent_id)

    context_pack = mock_context_engine.build_context_package(
        team_id=team_id,
        application_name=application_name,
        required_capabilities=required_ctx
    )

    skills_binding = mock_skills_engine.bind_skills_for_workflow(
        agent_id=agent_id,
        team_id=team_id,
        requested_skills=shortlist_skills
    )

    return {
        "agent_id": agent_id,
        "team_id": team_id,
        "required_context_capabilities": required_ctx,
        "context_package": context_pack,
        "skill_shortlist": shortlist_skills,
        "skills_binding": skills_binding
    }

