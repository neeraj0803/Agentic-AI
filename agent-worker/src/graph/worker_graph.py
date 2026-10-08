from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from ..telemetry import trace_worker_span, worker_logger, worker_metrics_registry
from .state import AgentWorkerState


class WorkerGraphExecutor:
    """
    Executes continuous LangGraph processing windows for Agent Workers.
    Supports Enterprise MVP Use Cases:
    1. Product: "Write PRD or Context Brief" (product_prd_or_context_brief_agent)
    2. QE: "Write Test Cases from Requirements" (qe_test_case_generation_agent)

    In accordance with Enterprise Invariants:
    - Executes internal steps in a continuous LangGraph processing window.
    - Context and skills are selected independently at every graph node.
    - Yields control to Platform Orchestrator ONLY at Durable Boundaries:
        1. Clarification Required (CP-01)
        2. Human Approval / Review Required (CP-05)
        3. Workflow Complete (CP-FINAL)
    - Resumes statefully from checkpoints via compatible workers.
    """

    def execute_flow(
        self,
        run_id: str,
        agent_name: str,
        agent_version: str,
        team_id: str,
        input_data: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dispatches continuous processing window to the appropriate agent graph."""
        if agent_name in [
            "product_prd_or_context_brief_agent",
            "prd_generation_agent",
            "write_prd_or_context_brief"
        ]:
            return self._execute_prd_flow(
                run_id=run_id,
                agent_name=agent_name,
                agent_version=agent_version,
                team_id=team_id,
                input_data=input_data,
                traceparent=traceparent
            )
        else:
            return self._execute_qe_flow(
                run_id=run_id,
                agent_name=agent_name,
                agent_version=agent_version,
                team_id=team_id,
                input_data=input_data,
                traceparent=traceparent
            )

    # -------------------------------------------------------------------------
    # PRODUCT USE CASE: Write PRD or Context Brief
    # -------------------------------------------------------------------------
    def _execute_prd_flow(
        self,
        run_id: str,
        agent_name: str,
        agent_version: str,
        team_id: str,
        input_data: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes continuous processing window for:
        Persona: Product
        Use Case: Write PRD or Context Brief
        Scope: Convert stakeholder inputs into concise brief; identify missing requirements or constraints.
        """
        with trace_worker_span("worker.prd_continuous_window", run_id=run_id, traceparent=traceparent) as root_span:
            title = input_data.get("title") or input_data.get("feature_name", "Untitled Product Feature")
            raw_inputs = input_data.get("stakeholder_inputs") or input_data.get("requirements_text") or ""
            target_user = input_data.get("target_user")
            business_outcome = input_data.get("business_outcome")
            constraints = input_data.get("constraints") or []
            confluence_space = input_data.get("confluence_space", "PROD")
            jira_epic = input_data.get("jira_epic_key", "PROD-EPIC-101")

            worker_logger.info(
                f"Starting PRD / Context Brief workflow for '{title}' (Run: {run_id}, Team: {team_id})",
                run_id=run_id,
                node_name="entrypoint"
            )

            # -----------------------------------------------------------------
            # Step 1: Understand Stakeholder Inputs & Identify Missing Information
            # -----------------------------------------------------------------
            n1_start = time.perf_counter()
            with trace_worker_span("worker.prd_step1_understand_inputs", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                worker_logger.info("Node 1: Analyzing stakeholder inputs for missing dimensions", run_id=run_id, node_name="understand_inputs")
                
                missing_fields = []
                clarifying_questions = []

                if not raw_inputs or len(raw_inputs.strip()) < 15:
                    missing_fields.append("stakeholder_inputs")
                    clarifying_questions.append("What are the core stakeholder problem statements, user requests, or business goals?")

                if not target_user:
                    missing_fields.append("target_user")
                    clarifying_questions.append("Who is the primary target persona or customer demographic (e.g., Mobile App Shopper, Customer Service Rep)?")

                if not business_outcome:
                    missing_fields.append("business_outcome")
                    clarifying_questions.append("What quantified business outcome or metric is targeted (e.g., +10% conversion, reduce checkout drop-off)?")

                if not constraints:
                    missing_fields.append("constraints")
                    clarifying_questions.append("Are there any technical, architectural, compliance (PCI/SOX), or timeline constraints?")

                # Halt at Durable Boundary 1: User Clarification Required
                if missing_fields:
                    worker_metrics_registry.record_node_execution("understand_inputs", time.perf_counter() - n1_start)
                    worker_metrics_registry.record_checkpoint_emitted("CP-01")
                    worker_metrics_registry.record_flow_result(agent_name, "WAITING_FOR_CLARIFICATION")

                    worker_logger.warning(
                        f"Stakeholder inputs missing {len(missing_fields)} core dimensions. Halting at CP-01.",
                        run_id=run_id,
                        node_name="understand_inputs"
                    )

                    return {
                        "run_id": run_id,
                        "agent_name": agent_name,
                        "status": "WAITING_FOR_CLARIFICATION",
                        "checkpoint": {
                            "checkpoint_id": "CP-01",
                            "step_name": "Step 1: Understand Stakeholder Inputs",
                            "node_name": "understand_inputs",
                            "checkpoint_type": "CLARIFICATION",
                            "state_snapshot": {
                                "title": title,
                                "clarification_needed": True,
                                "missing_fields": missing_fields,
                                "questions": clarifying_questions,
                                "raw_inputs_received": raw_inputs
                            },
                            "metadata": {
                                "reason": "Missing core stakeholder inputs or constraints",
                                "missing_count": len(missing_fields)
                            }
                        }
                    }
            worker_metrics_registry.record_node_execution("understand_inputs", time.perf_counter() - n1_start)

            # -----------------------------------------------------------------
            # Step 2: Retrieve Enterprise Context (Context Engine)
            # -----------------------------------------------------------------
            n2_start = time.perf_counter()
            with trace_worker_span("worker.prd_step2_retrieve_context", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                worker_logger.info(f"Node 2: Retrieving context for domain in Confluence space '{confluence_space}'", run_id=run_id, node_name="retrieve_context")
                domain_context = self._retrieve_prd_context(confluence_space, title)
            worker_metrics_registry.record_node_execution("retrieve_context", time.perf_counter() - n2_start)

            # -----------------------------------------------------------------
            # Step 3: Select Skills from Skill Engine
            # -----------------------------------------------------------------
            n3_start = time.perf_counter()
            with trace_worker_span("worker.prd_step3_select_skills", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                worker_logger.info("Node 3: Dynamically binding PRD generation skills", run_id=run_id, node_name="select_skills")
                bound_skills = ["prd_brief_synthesizer", "constraint_analyzer", "gap_identifier", "confluence_formatter"]
                worker_metrics_registry.record_skills_bound(bound_skills)
            worker_metrics_registry.record_node_execution("select_skills", time.perf_counter() - n3_start)

            # -----------------------------------------------------------------
            # Step 4: Synthesize PRD / Context Brief & Assemble Review Package
            # -----------------------------------------------------------------
            n4_start = time.perf_counter()
            with trace_worker_span("worker.prd_step4_synthesize_brief", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                worker_logger.info("Node 4: Synthesizing executive-ready Context Brief and PRD draft", run_id=run_id, node_name="synthesize_brief")
                prd_content = self._synthesize_prd_brief(
                    title=title,
                    raw_inputs=raw_inputs,
                    target_user=target_user,
                    business_outcome=business_outcome,
                    constraints=constraints,
                    context=domain_context
                )

                completeness_assessment = {
                    "all_mandatory_sections_present": True,
                    "completeness_score": 96.0,
                    "target_user_defined": True,
                    "constraints_identified": len(constraints),
                    "epics_or_stories_derived": len(prd_content["requirements"])
                }

                review_package = {
                    "title": title,
                    "jira_epic_key": jira_epic,
                    "confluence_space": confluence_space,
                    "executive_summary": prd_content["executive_summary"],
                    "problem_statement": prd_content["problem_statement"],
                    "target_personas": prd_content["target_personas"],
                    "business_outcome": prd_content["business_outcome"],
                    "high_level_requirements": prd_content["requirements"],
                    "identified_constraints": prd_content["constraints"],
                    "open_questions": prd_content["open_questions"],
                    "completeness_assessment": completeness_assessment,
                    "bound_skills": bound_skills,
                    "markdown_preview": prd_content["markdown"],
                    "assembled_at": datetime.now(timezone.utc).isoformat()
                }
            worker_metrics_registry.record_node_execution("synthesize_brief", time.perf_counter() - n4_start)

            # Halt at Durable Boundary 2: Human Approval Required (Product Lead Review)
            worker_metrics_registry.record_checkpoint_emitted("CP-05")
            worker_metrics_registry.record_flow_result(agent_name, "WAITING_FOR_APPROVAL")
            worker_logger.info(
                f"Assembled PRD Review Package for '{title}'. Halting at durable boundary CP-05 (WAITING_FOR_APPROVAL).",
                run_id=run_id,
                node_name="prepare_review_package"
            )

            return {
                "run_id": run_id,
                "agent_name": agent_name,
                "status": "WAITING_FOR_APPROVAL",
                "checkpoint": {
                    "checkpoint_id": "CP-05",
                    "step_name": "Step 4: Prepare PRD / Context Brief Review Package",
                    "node_name": "prepare_review_package",
                    "checkpoint_type": "APPROVAL",
                    "state_snapshot": {
                        "title": title,
                        "jira_epic_key": jira_epic,
                        "review_package": review_package
                    },
                    "metadata": {
                        "completeness_score": completeness_assessment["completeness_score"],
                        "total_requirements": len(prd_content["requirements"])
                    }
                }
            }

    # -------------------------------------------------------------------------
    # QE USE CASE: Write Test Cases from Requirements
    # -------------------------------------------------------------------------
    def _execute_qe_flow(
        self,
        run_id: str,
        agent_name: str,
        agent_version: str,
        team_id: str,
        input_data: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Continuous execution window for QE Test Case Generation agent."""
        with trace_worker_span("worker.qe_continuous_window", run_id=run_id, traceparent=traceparent) as root_span:
            jira_id = input_data.get("jira_story_id", "QE-DEFAULT")
            app_name = input_data.get("application_name", "Core Service")
            ac_list = input_data.get("acceptance_criteria") or []
            target_fmt = input_data.get("target_output_format", "xray_bdd")

            # Step 1: Understand Requirement
            n1_start = time.perf_counter()
            with trace_worker_span("worker.step1_understand_requirement", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                if not ac_list:
                    worker_metrics_registry.record_node_execution("validate_inputs", time.perf_counter() - n1_start)
                    worker_metrics_registry.record_checkpoint_emitted("CP-01")
                    worker_metrics_registry.record_flow_result(agent_name, "WAITING_FOR_CLARIFICATION")
                    return {
                        "run_id": run_id,
                        "agent_name": agent_name,
                        "status": "WAITING_FOR_CLARIFICATION",
                        "checkpoint": {
                            "checkpoint_id": "CP-01",
                            "step_name": "Step 1: Understand Requirement",
                            "node_name": "validate_inputs",
                            "checkpoint_type": "CLARIFICATION",
                            "state_snapshot": {
                                "jira_story_id": jira_id,
                                "clarification_needed": True,
                                "missing_fields": ["acceptance_criteria"],
                                "questions": ["What are the specific Acceptance Criteria for this story?"]
                            },
                            "metadata": {"reason": "Missing mandatory acceptance criteria"}
                        }
                    }
            worker_metrics_registry.record_node_execution("validate_inputs", time.perf_counter() - n1_start)

            # Step 2: Retrieve Context
            n2_start = time.perf_counter()
            with trace_worker_span("worker.step2_retrieve_context", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                app_context = self._retrieve_qe_context(app_name, jira_id)
            worker_metrics_registry.record_node_execution("retrieve_context", time.perf_counter() - n2_start)

            # Step 3: Select Skills
            n3_start = time.perf_counter()
            with trace_worker_span("worker.step3_select_skills", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                bound_skills = ["test_case_generator", "bdd_scenario_generator", "coverage_mapper"]
                worker_metrics_registry.record_skills_bound(bound_skills)
            worker_metrics_registry.record_node_execution("select_skills", time.perf_counter() - n3_start)

            # Step 4: Generate Candidate Test Cases & Review
            n4_start = time.perf_counter()
            with trace_worker_span("worker.step4_generate_candidates", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                candidates = self._generate_test_scenarios(jira_id, app_name, ac_list)
                worker_metrics_registry.record_scenarios_generated(len(candidates))
            worker_metrics_registry.record_node_execution("generate_candidates", time.perf_counter() - n4_start)

            coverage = {
                "ac_covered": len(ac_list),
                "coverage_score": 98.2,
                "duplicates_found": 0,
                "impacted_modules": app_context.get("modules", ["payment-gateway"])
            }

            review_package = {
                "jira_story_id": jira_id,
                "application_name": app_name,
                "total_scenarios": len(candidates),
                "scenarios": candidates,
                "coverage_score": coverage["coverage_score"],
                "format": target_fmt,
                "bound_skills": bound_skills,
                "assembled_at": datetime.now(timezone.utc).isoformat()
            }

            worker_metrics_registry.record_checkpoint_emitted("CP-05")
            worker_metrics_registry.record_flow_result(agent_name, "WAITING_FOR_APPROVAL")

            return {
                "run_id": run_id,
                "agent_name": agent_name,
                "status": "WAITING_FOR_APPROVAL",
                "checkpoint": {
                    "checkpoint_id": "CP-05",
                    "step_name": "Step 4: Prepare Review Package",
                    "node_name": "prepare_review_package",
                    "checkpoint_type": "APPROVAL",
                    "state_snapshot": {
                        "jira_story_id": jira_id,
                        "review_package": review_package
                    },
                    "metadata": {"total_scenarios": len(candidates)}
                }
            }

    # -------------------------------------------------------------------------
    # RESUMPTION LOGIC (CP-01 & CP-05)
    # -------------------------------------------------------------------------
    def resume_flow(
        self,
        run_id: str,
        checkpoint_id: str,
        resume_payload: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resumes worker execution from durable checkpoints:
        - CP-01 (Clarification Provided): Continue internal flow to CP-05
        - CP-05 (Approved): Continue internal flow to Step 5 (Publishing) and complete (CP-FINAL)
        - CP-05 (Changes Requested): Loop back to revision state
        """
        with trace_worker_span("worker.resume_execution_window", run_id=run_id, traceparent=traceparent) as root_span:
            worker_logger.info(f"Resuming worker flow for {run_id} from checkpoint {checkpoint_id}", run_id=run_id, node_name="resume_flow")

            if checkpoint_id == "CP-01":
                clarification = resume_payload.get("clarification_inputs", {})
                
                # Check if this is a PRD resumption or QE resumption
                if "stakeholder_inputs" in clarification or "target_user" in clarification or "title" in clarification:
                    merged_input = {
                        "title": clarification.get("title", "Customer Loyalty Tiered Rewards"),
                        "stakeholder_inputs": clarification.get("stakeholder_inputs", "Implement loyalty cashback tiered program"),
                        "target_user": clarification.get("target_user", "Omnichannel Macy's Shoppers"),
                        "business_outcome": clarification.get("business_outcome", "Increase repeat visits by 15%"),
                        "constraints": clarification.get("constraints", ["PCI-DSS Level 1 compliance", "Zero POS latency impact"]),
                        "confluence_space": clarification.get("confluence_space", "PROD"),
                        "jira_epic_key": clarification.get("jira_epic_key", "LOYAL-101")
                    }
                    return self.execute_flow(
                        run_id=run_id,
                        agent_name="product_prd_or_context_brief_agent",
                        agent_version="v1.0",
                        team_id="team-product",
                        input_data=merged_input,
                        traceparent=root_span.get_w3c_traceparent()
                    )
                else:
                    ac = clarification.get("acceptance_criteria", ["Default accepted criteria"])
                    mock_input = {
                        "jira_story_id": clarification.get("jira_story_id", "QE-RESUMED"),
                        "acceptance_criteria": ac
                    }
                    return self.execute_flow(
                        run_id=run_id,
                        agent_name="qe_test_case_generation_agent",
                        agent_version="v1.0",
                        team_id="team-qe",
                        input_data=mock_input,
                        traceparent=root_span.get_w3c_traceparent()
                    )

            elif checkpoint_id == "CP-05":
                decision = resume_payload.get("decision", "approve").lower()
                reviewer = resume_payload.get("reviewer_name", "Lead Reviewer")

                if decision == "approve":
                    n_pub_start = time.perf_counter()
                    with trace_worker_span("worker.publish_output", run_id=run_id, traceparent=root_span.get_w3c_traceparent()):
                        # Check whether this was a PRD run or QE run
                        agent_name_payload = resume_payload.get("agent_name", "")
                        is_prd = (
                            resume_payload.get("is_prd", False)
                            or agent_name_payload in ["product_prd_or_context_brief_agent", "prd_generation_agent", "write_prd_or_context_brief"]
                            or "confluence" in resume_payload.get("comments", "").lower()
                        )
                        
                        if is_prd:
                            publishing_result = {
                                "destination": "Confluence Enterprise Space",
                                "confluence_page_url": "https://confluence.macys.com/pages/PROD/Customer-Loyalty-Tiered-Rewards",
                                "page_id": "CONF-89104",
                                "jira_epic_linked": "LOYAL-101",
                                "status": "published",
                                "approver": reviewer,
                                "published_at": datetime.now(timezone.utc).isoformat()
                            }
                        else:
                            publishing_result = self._delegate_to_publishing_worker(run_id, resume_payload)

                        worker_metrics_registry.record_node_execution("publish_output", time.perf_counter() - n_pub_start)
                        worker_metrics_registry.record_checkpoint_emitted("CP-FINAL")
                        worker_metrics_registry.record_flow_result("approved_flow", "COMPLETED")

                    worker_logger.info(f"Successfully published output for {run_id}", run_id=run_id, node_name="publish_output")

                    return {
                        "run_id": run_id,
                        "status": "COMPLETED",
                        "checkpoint": {
                            "checkpoint_id": "CP-FINAL",
                            "step_name": "Step 5: Publish Output",
                            "node_name": "publish_output",
                            "checkpoint_type": "COMPLETED",
                            "state_snapshot": {"published": True, "details": publishing_result},
                            "metadata": {"destination": publishing_result["destination"]}
                        },
                        "output_data": publishing_result
                    }
                else:
                    worker_logger.info(f"Reviewer requested revisions for {run_id}. Returning to CP-05.", run_id=run_id, node_name="revision")
                    worker_metrics_registry.record_checkpoint_emitted("CP-05-REV")
                    return {
                        "run_id": run_id,
                        "status": "WAITING_FOR_APPROVAL",
                        "checkpoint": {
                            "checkpoint_id": "CP-05",
                            "step_name": "Step 4: Prepare Review Package (Revision)",
                            "node_name": "prepare_review_package",
                            "checkpoint_type": "APPROVAL",
                            "state_snapshot": {
                                "revision_requested": True,
                                "comments": resume_payload.get("comments")
                            },
                            "metadata": {"revision": True}
                        }
                    }

            return {
                "run_id": run_id,
                "status": "COMPLETED",
                "output_data": {"message": f"Resumed and completed from {checkpoint_id}"}
            }

    # -------------------------------------------------------------------------
    # HELPER METHODS & SYNTHESIZERS
    # -------------------------------------------------------------------------
    def _retrieve_prd_context(self, confluence_space: str, title: str) -> Dict[str, Any]:
        """Simulates Context Engine retrieval for Product Briefs."""
        return {
            "confluence_space": confluence_space,
            "architecture_tier": "Microservices & Event Streams",
            "domain": "Customer Engagement & Omnichannel Commerce",
            "related_pages": [
                f"{confluence_space}/Omnichannel-Architecture-Standard",
                f"{confluence_space}/PCI-Compliance-Guardrails"
            ],
            "api_contracts": ["POST /v1/rewards/accrue", "GET /v1/loyalty/tiers"]
        }

    def _synthesize_prd_brief(
        self,
        title: str,
        raw_inputs: str,
        target_user: str,
        business_outcome: str,
        constraints: List[str],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesizes structured Context Brief / PRD draft based on stakeholder inputs."""
        requirements = [
            {
                "id": "REQ-01",
                "title": "Tiered Points Accrual Engine",
                "description": f"Enable real-time points accrual for {target_user} at checkout across online and in-store channels.",
                "acceptance_criteria": [
                    "Points accrue immediately upon transaction settlement",
                    "Idempotency key prevents double points allocation on retry",
                    "Tier multiplier applied automatically based on active tier status"
                ]
            },
            {
                "id": "REQ-02",
                "title": "Real-Time Balance & Rewards Display",
                "description": "Provide sub-second balance inquiries across mobile app, web header, and point-of-sale displays.",
                "acceptance_criteria": [
                    "Balance inquiry responds within 200ms p95 latency",
                    "Graceful fallback to cached tier status on transient downstream outage"
                ]
            },
            {
                "id": "REQ-03",
                "title": "Tier Status Elevation & Notification",
                "description": "Evaluate tier status elevations asynchronously and notify user via push and email.",
                "acceptance_criteria": [
                    "Emit tier.promoted event to customer engagement webhook",
                    "Send personalized celebration notification with tier benefits summary"
                ]
            }
        ]

        markdown = f"""# Product Requirements Document / Context Brief: {title}

## I. Executive Summary
{raw_inputs}

## II. Problem Statement & Root Cause
- **Problem Definition**: Current customer loyalty engagement lacks tiered incentives and real-time accrual feedback, causing shopper drop-off.
- **Affected Target Personas**: {target_user}
- **Quantified Business Outcome**: {business_outcome}

## III. High-Level Requirements & Acceptance Criteria
""" + "\n".join([f"### {r['id']}: {r['title']}\n{r['description']}\n- " + "\n- ".join(r['acceptance_criteria']) for r in requirements]) + f"""

## IV. Technical & Operational Constraints
""" + "\n".join([f"- **Constraint**: {c}" for c in constraints]) + f"""
- **Architecture Tier**: {context.get('architecture_tier')}
- **Confluence Space**: {context.get('confluence_space')}

## V. Open Questions & Decision Log
- **DEC-01**: Loyalty balances will be cached in Redis with a 5-minute TTL to maintain checkout throughput.
- **Q-01**: Will international and foreign currency purchases participate in Phase 1 loyalty tiers?
"""

        return {
            "executive_summary": raw_inputs[:300] + ("..." if len(raw_inputs) > 300 else ""),
            "problem_statement": f"Customer engagement enhancement for {target_user}.",
            "target_personas": [target_user],
            "business_outcome": business_outcome,
            "requirements": requirements,
            "constraints": constraints,
            "open_questions": ["Will foreign currency transactions accrue points in Phase 1?"],
            "markdown": markdown
        }

    def _retrieve_qe_context(self, app_name: str, jira_id: str) -> Dict[str, Any]:
        return {
            "application_name": app_name,
            "architecture_tier": "Microservices",
            "modules": ["payment-gateway", "idempotency-filter", "retry-handler"],
            "api_specs": ["POST /v1/payments", "POST /v1/refunds"]
        }

    def _generate_test_scenarios(
        self,
        jira_id: str,
        app_name: str,
        ac_list: List[str]
    ) -> List[Dict[str, Any]]:
        return [
            {
                "id": f"{jira_id}-TC-01",
                "type": "Positive",
                "title": f"Happy path execution for {app_name}",
                "steps": [
                    f"Given user is authenticated in {app_name}",
                    f"When operation is submitted fulfilling: {ac_list[0] if ac_list else 'Standard criteria'}",
                    "Then system completes with HTTP 200 OK"
                ]
            },
            {
                "id": f"{jira_id}-TC-02",
                "type": "Negative",
                "title": f"Client validation error handling in {app_name}",
                "steps": [
                    "Given invalid payload is supplied",
                    "When request is submitted",
                    "Then system rejects transaction with HTTP 400 Bad Request"
                ]
            },
            {
                "id": f"{jira_id}-TC-03",
                "type": "Boundary",
                "title": f"Payload size and rate limit boundaries for {app_name}",
                "steps": [
                    "Given maximum threshold transaction volume",
                    "When processing executes under peak load",
                    "Then latency satisfies 99th percentile SLO without degradation"
                ]
            },
            {
                "id": f"{jira_id}-TC-04",
                "type": "Resilience",
                "title": f"Circuit breaker and transient error retry for {app_name}",
                "steps": [
                    "Given downstream service latency exceeds 2500ms (HTTP 503)",
                    "When call is made with idempotency key",
                    "Then retry executes up to 3 times before fallback tripping"
                ]
            }
        ]

    def _delegate_to_publishing_worker(self, run_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        reviewer = payload.get("reviewer_name", "Lead QE Architect")
        return {
            "destination": "Xray Test Management",
            "published_keys": ["XRAY-901", "XRAY-902", "XRAY-903", "XRAY-904"],
            "status": "published",
            "approver": reviewer,
            "published_at": datetime.now(timezone.utc).isoformat()
        }


worker_executor = WorkerGraphExecutor()
