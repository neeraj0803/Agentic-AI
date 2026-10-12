import hashlib
import json
import time
from typing import Any, Dict, List, Optional
import uuid
import yaml

from .workflow_registry import workflow_registry
from ..telemetry import logger


class SnapshotCompilationService:
    """
    Resolved Workflow Snapshot Compiler.
    Compiles:
    1. Immutable published workflow YAML
    2. Platform governance & model policies
    3. Team connector bindings & overrides
    4. Runtime context & skill overlays
    Calculates SHA-256 integrity hash and assigns resolved_workflow_id (rwf_*).
    """

    def compile_snapshot(
        self,
        agent_identifier: Optional[str] = None,
        team_id: str = "team-checkout-qe",
        policy_version: str = "2026.Q3",
        context_overlays: Optional[List[str]] = None,
        skill_overlays: Optional[List[str]] = None,
        user_overrides: Optional[Dict[str, Any]] = None,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compiles immutable resolved workflow snapshot."""
        target_id = agent_identifier or workflow_id
        if not target_id:
            raise ValueError("Cannot compile snapshot: Missing agent_identifier or workflow_id.")

        wf = workflow_registry.get_workflow(target_id)
        if not wf:
            raise ValueError(f"Cannot compile snapshot: Workflow '{target_id}' not found.")

        resolved_wf_id = f"rwf_{uuid.uuid4().hex[:16]}"
        wf_yaml_str = yaml.dump(wf, sort_keys=True)

        policy_snapshot = {
            "policy_version": policy_version,
            "team_id": team_id,
            "model_policy_ref": wf.get("model_policy_ref", "standard_gemini"),
            "max_rework_cycles": 3,
            "max_validation_attempts": 3,
            "guardrail_profile": "model_armor_enterprise_v2"
        }

        team_config_snapshot = {
            "team_id": team_id,
            "context_overlays": context_overlays or [],
            "skill_overlays": skill_overlays or [],
            "user_overrides": user_overrides or {}
        }

        step_bindings = {}
        for node in wf.get("graph", {}).get("nodes", []):
            node_id = node.get("id")
            step_bindings[node_id] = {
                "type": node.get("type"),
                "checkpoint": node.get("checkpoint", "none"),
                "connector_ref": node.get("connector_ref")
            }

        # Calculate SHA256 integrity hash
        canonical_str = json.dumps({
            "yaml": wf_yaml_str,
            "policy": policy_snapshot,
            "team_config": team_config_snapshot,
            "step_bindings": step_bindings
        }, sort_keys=True)
        sha256_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        snapshot = {
            "resolved_workflow_id": resolved_wf_id,
            "workflow_id": wf.get("workflow_id"),
            "agent_id": wf.get("agent", {}).get("id"),
            "workflow_version": wf.get("version", "1.0.0"),
            "sha256_hash": sha256_hash,
            "workflow_yaml": wf_yaml_str,
            "policy_snapshot": policy_snapshot,
            "team_config_snapshot": team_config_snapshot,
            "step_bindings_map": step_bindings,
            "created_at": time.time()
        }

        logger.info(f"SnapshotCompiler: Compiled snapshot {resolved_wf_id} for {agent_identifier} (Hash: {sha256_hash[:8]}...)")
        return snapshot


snapshot_service = SnapshotCompilationService()
