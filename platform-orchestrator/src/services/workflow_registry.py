import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from ..telemetry import logger


class WorkflowRegistry:
    """
    Workflow Definition Registry for Platform Orchestrator.
    Loads, validates, and serves immutable published workflow definitions authored in YAML.
    Extracts agent schemas, required inputs, context capabilities, and skill candidate lists.
    """

    def __init__(self, workflows_dir: Optional[str] = None):
        if workflows_dir:
            self.workflows_dir = Path(workflows_dir)
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.workflows_dir = base_dir / "workflows"

        self._workflows: Dict[str, Dict[str, Any]] = {}
        self._agent_to_workflow: Dict[str, str] = {}
        self.load_workflows()

    def load_workflows(self) -> None:
        """Loads and parses all YAML files in the workflows directory."""
        if not self.workflows_dir.exists():
            logger.warning(f"Workflows directory '{self.workflows_dir}' not found. Initializing empty registry.")
            return

        self._workflows.clear()
        self._agent_to_workflow.clear()

        for file_path in self.workflows_dir.glob("*.yaml"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if not data or not isinstance(data, dict):
                        continue

                    wf_id = data.get("workflow_id")
                    agent_info = data.get("agent", {})
                    agent_id = agent_info.get("id")

                    if wf_id:
                        self._workflows[wf_id] = data
                        if agent_id:
                            self._agent_to_workflow[agent_id.upper()] = wf_id
                            self._agent_to_workflow[agent_info.get("name", "").lower()] = wf_id
                        logger.info(f"Loaded published workflow YAML: {wf_id} [Agent: {agent_id}]")
            except Exception as e:
                logger.error(f"Failed to parse workflow file '{file_path}': {e}")

    def get_workflow(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Retrieves workflow definition by workflow_id, agent_id (e.g. AG-101), or agent name."""
        if not identifier:
            return None

        # Direct match by workflow_id
        if identifier in self._workflows:
            return self._workflows[identifier]

        # Match legacy agent aliases
        aliases = {
            "qe_test_case_generation_agent": "AG-201-write-test-cases",
            "prd_generation_agent": "AG-101-prd-generation",
            "code_generation_agent": "AG-301-code-generation",
            "architecture_adr_agent": "AG-501-architecture-adr",
        }
        if identifier.lower() in aliases:
            target_wf_id = aliases[identifier.lower()]
            if target_wf_id in self._workflows:
                return self._workflows[target_wf_id]

        # Match by agent_id (case-insensitive)
        upper_id = identifier.upper()
        if upper_id in self._agent_to_workflow:
            wf_id = self._agent_to_workflow[upper_id]
            return self._workflows.get(wf_id)

        # Match by agent name (case-insensitive)
        lower_name = identifier.lower().replace(" ", "_")
        for key, wf_id in self._agent_to_workflow.items():
            if lower_name in key or key in lower_name:
                return self._workflows.get(wf_id)

        return None

    def list_workflows(self) -> List[Dict[str, Any]]:
        """Returns summary of all published workflows."""
        summaries = []
        for wf_id, wf in self._workflows.items():
            agent = wf.get("agent", {})
            summaries.append({
                "workflow_id": wf_id,
                "version": wf.get("version", "1.0.0"),
                "status": wf.get("status", "published"),
                "agent_id": agent.get("id"),
                "agent_name": agent.get("name"),
                "domain": agent.get("domain"),
                "description": agent.get("description"),
                "channels": wf.get("channels", {}).get("allowed", []),
                "run_modes": wf.get("run_modes", {})
            })
        return summaries

    def get_context_and_skills_for_agent(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Extracts context capabilities, packs, and skill candidate list for an agent."""
        wf = self.get_workflow(identifier)
        if not wf:
            return None

        agent = wf.get("agent", {})
        context_def = wf.get("context", {})
        skills_def = wf.get("skills", {})

        return {
            "agent_id": agent.get("id"),
            "agent_name": agent.get("name"),
            "workflow_id": wf.get("workflow_id"),
            "context_capabilities_required": context_def.get("required_capabilities", []),
            "available_context_packs": context_def.get("available_packs", []),
            "required_skills": skills_def.get("required", []),
            "available_dynamic_skills": skills_def.get("available_dynamic", []),
            "model_policy_ref": wf.get("model_policy_ref")
        }

    def validate_inputs(self, identifier: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates provided input payload against required inputs in the workflow definition."""
        wf = self.get_workflow(identifier)
        if not wf:
            return {"valid": False, "error": f"Workflow '{identifier}' not found."}

        required_inputs = wf.get("inputs", [])
        missing_fields = []
        validated_inputs = {}

        # Normalize common aliases: synthesize requirement_ref if jira_story_id or acceptance_criteria present
        normalized_data = dict(input_data)
        if "requirement_ref" not in normalized_data:
            if "jira_story_id" in normalized_data or "acceptance_criteria" in normalized_data:
                parts = []
                if "jira_story_id" in normalized_data:
                    parts.append(str(normalized_data["jira_story_id"]))
                if "application_name" in normalized_data:
                    parts.append(str(normalized_data["application_name"]))
                if "acceptance_criteria" in normalized_data:
                    ac = normalized_data["acceptance_criteria"]
                    if isinstance(ac, list):
                        parts.append("; ".join(str(x) for x in ac))
                    else:
                        parts.append(str(ac))
                normalized_data["requirement_ref"] = " - ".join(parts)

        for inp in required_inputs:
            inp_id = inp.get("id")
            is_req = inp.get("required", False)
            prompt = inp.get("prompt", "")
            default_val = inp.get("default")

            if inp_id in normalized_data and normalized_data[inp_id] not in (None, ""):
                val = normalized_data[inp_id]
                # Validate min length if configured
                val_rule = inp.get("validation", {})
                if val_rule.get("kind") == "min_length" and isinstance(val, str):
                    min_len = val_rule.get("min_length", 1)
                    if len(val.strip()) < min_len:
                        return {
                            "valid": False,
                            "error": f"Field '{inp_id}' is too short (min {min_len} characters required).",
                            "field": inp_id
                        }
                validated_inputs[inp_id] = val
            elif default_val is not None:
                validated_inputs[inp_id] = default_val
            elif is_req:
                missing_fields.append({
                    "field_id": inp_id,
                    "prompt": prompt,
                    "type": inp.get("type", "string")
                })

        if missing_fields:
            return {
                "valid": False,
                "missing_fields": missing_fields,
                "error": f"Missing {len(missing_fields)} required input field(s)."
            }

        return {"valid": True, "validated_inputs": validated_inputs}

    def validate_input_payload(self, identifier: str, input_data: Dict[str, Any]) -> List[str]:
        """Returns list of missing required field names."""
        res = self.validate_inputs(identifier, input_data)
        if res.get("valid"):
            return []
        missing = res.get("missing_fields", [])
        return [m.get("field_id") for m in missing]

    def extract_required_context(self, identifier: str) -> List[str]:
        """Extracts required context capabilities for the workflow."""
        details = self.get_context_and_skills_for_agent(identifier)
        return details.get("context_capabilities_required", []) if details else []

    def extract_skill_shortlist(self, identifier: str) -> List[str]:
        """Extracts required skills for the workflow."""
        details = self.get_context_and_skills_for_agent(identifier)
        return details.get("required_skills", []) if details else []


workflow_registry = WorkflowRegistry()

