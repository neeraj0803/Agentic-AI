from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Dict[str, Any]


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class DiscoverSkillsFilter(BaseModel):
    capability_need: Optional[str] = None
    domain: Optional[str] = None
    sdlc_phase: Optional[str] = None
    governance_status: Optional[str] = "approved"
    lifecycle_status: Optional[str] = "active"


class DiscoverSkillsParams(BaseModel):
    name: str = "discover_skills"
    arguments: Dict[str, Any]


class PrismContextRetrieveParams(BaseModel):
    name: str = "prism.context.retrieve"
    arguments: Dict[str, Any]

