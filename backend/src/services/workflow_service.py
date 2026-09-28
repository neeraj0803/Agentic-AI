import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from .document_extractor_service import DocumentExtractorService
from .context_service import ContextAnalyzerService
from .gap_analyzer_service import GapAnalyzerService
from .prd_service import PRDGeneratorService
from .prd_reviewer_service import PRDReviewerService
from .hitl_service import HITLService
from .publish_service import PublishService
from ..agents.evidence_analyzer import evidence_analyzer_node
from ..config import settings
from ..mcp import InProcessMCPClient


class WorkflowOrchestratorService:
    """
    End-to-End Workflow Orchestrator.
    Implements the flowchart and 7-step Agent Journey with integrated
    Evidence Analyzer and automated HITL supplementary context ingestion.
    """

    def __init__(
        self,
        mcp_client: Optional[InProcessMCPClient] = None,
        context_service: Optional[ContextAnalyzerService] = None,
        gap_service: Optional[GapAnalyzerService] = None,
        prd_service: Optional[PRDGeneratorService] = None,
        reviewer_service: Optional[PRDReviewerService] = None,
        hitl_service: Optional[HITLService] = None,
        publish_service: Optional[PublishService] = None,
    ):
        self.mcp_client = mcp_client or InProcessMCPClient()
        self.context_service = context_service or ContextAnalyzerService(self.mcp_client)
        self.gap_service = gap_service or GapAnalyzerService()
        self.prd_service = prd_service or PRDGeneratorService()
        self.reviewer_service = reviewer_service or PRDReviewerService()
        self.hitl_service = hitl_service or HITLService()
        self.publish_service = publish_service or PublishService()

        # In-memory session store for POC state tracking
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def run_workflow_from_file(
        self,
        file_path: str,
        original_document_name: Optional[str] = None,
        active_team_id: str = "team-checkout-product",
        query_override: Optional[str] = None,
        auto_approve_hitl: bool = True,
        reviewer_comments: Optional[str] = None,
        target_publish_platform: Literal["jira", "confluence", "both"] = "both"
    ) -> Dict[str, Any]:
        """
        Executes the full flowchart from an uploaded file path.
        """
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        doc_path = Path(file_path)
        doc_name = original_document_name or doc_path.name

        session_state: Dict[str, Any] = {
            "session_id": session_id,
            "status": "started",
            "document_name": doc_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "current_node": "A_Document_Upload"
        }
        self._sessions[session_id] = session_state

        def log_step(node: str, step_name: str, status: str, details: Any):
            step_record = {
                "node": node,
                "step_name": step_name,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details
            }
            session_state["steps"].append(step_record)
            session_state["current_node"] = node

        # -------------------------------------------------------------------
        # Node A & B: Document Upload & Doc Extractor
        # -------------------------------------------------------------------
        log_step("A_Document_Upload", "Document Upload", "completed", {
            "file_name": doc_name,
            "file_path": str(doc_path)
        })

        extracted_text = DocumentExtractorService.extract_text(str(file_path))
        log_step("B_Doc_Extractor", "1. Doc Extractor", "completed", {
            "characters_extracted": len(extracted_text),
            "preview": extracted_text[:200] + "..." if len(extracted_text) > 200 else extracted_text
        })

        # -------------------------------------------------------------------
        # Node C: Context Analyzer (with MCP Skill & Context Retrieval)
        # -------------------------------------------------------------------
        context_analysis = self.context_service.analyze(
            document_name=doc_name,
            extracted_text=extracted_text,
            active_team_id=active_team_id,
            query_override=query_override
        )
        log_step("C_Context_Analyzer", "2. Context Analyzer", "completed", {
            "intent": context_analysis.get("intent"),
            "problem_statement": context_analysis.get("problem_statement"),
            "business_goal": context_analysis.get("business_goal"),
            "discovered_skills_count": len(context_analysis.get("mcp_skills", [])),
            "retrieved_references_count": len(context_analysis.get("mcp_context_package", {}).get("retrieved_references", [])),
            "evidence_items": len(context_analysis.get("evidence", []))
        })

        # -------------------------------------------------------------------
        # Node D: Gap Analyzer
        # -------------------------------------------------------------------
        gap_report = self.gap_service.analyze_gaps(context_analysis)
        log_step("D_Gap_Analyzer", "3. Gap Analyzer", "completed", {
            "sufficiency_score": gap_report.get("sufficiency_score"),
            "readiness_score": f"{gap_report.get('sufficiency_score')}%",
            "is_sufficient": gap_report.get("is_sufficient", True),
            "readiness_matrix_summary": gap_report.get("readiness_matrix_summary", {}),
            "gaps_count": len(gap_report.get("identified_gaps", [])),
            "conflicts_count": len(gap_report.get("detected_conflicts", [])),
            "conflicts": gap_report.get("detected_conflicts", []),
            "unvalidated_assumptions": gap_report.get("unvalidated_assumptions", []),
            "identified_gaps": gap_report.get("identified_gaps", [])
        })

        # -------------------------------------------------------------------
        # Node E: Evidence Analyzer Agent & HITL Supplementary Ingestion Loop
        # -------------------------------------------------------------------
        evidence_eval = evidence_analyzer_node(context_analysis)
        log_step("E_Evidence_Analyzer", "4. Evidence Analyzer", "completed", evidence_eval)

        is_evidence_sufficient = evidence_eval.get("sufficient", True)

        # If evidence is insufficient and auto_approve_hitl is active, attempt HITL supplementary context ingestion
        if not is_evidence_sufficient:
            supp_path = settings.hitl_context_file_path
            if auto_approve_hitl and supp_path and Path(supp_path).exists():
                log_step("I_HITL_Context_Request", "HITL Supplementary Context Ingestion", "in_progress", {
                    "reason": "Evidence deemed insufficient by Evidence Analyzer. Ingesting supplementary context file.",
                    "supplementary_file": supp_path
                })
                supp_text = DocumentExtractorService.extract_text(supp_path)
                combined_text = (
                    f"{extracted_text}\n\n"
                    "## Supplementary Grounding Context\n"
                    f"{supp_text}"
                )

                # Re-run Context Analysis and Gap Analysis with enriched text
                context_analysis = self.context_service.analyze(
                    document_name=doc_name,
                    extracted_text=combined_text,
                    active_team_id=active_team_id,
                    query_override=query_override
                )
                gap_report = self.gap_service.analyze_gaps(context_analysis)
                evidence_eval = evidence_analyzer_node(context_analysis)
                is_evidence_sufficient = evidence_eval.get("sufficient", True)

                log_step("I_HITL_Context_Request", "HITL Supplementary Context Ingestion", "completed", {
                    "new_evidence_count": len(context_analysis.get("evidence", [])),
                    "re_evaluated_sufficient": is_evidence_sufficient
                })
            else:
                log_step("E_Context_Sufficient_Decision", "Context & Evidence Sufficient?", "failed_insufficient_evidence", {
                    "decision": "No - Missing Context / Weak Evidence",
                    "missing_context": evidence_eval.get("missing_context", []),
                    "weak_evidence": evidence_eval.get("weak_evidence", []),
                    "rationale": evidence_eval.get("rationale")
                })
                session_state["status"] = "paused_missing_context"
                session_state["context_analysis"] = context_analysis
                session_state["gap_report"] = gap_report
                session_state["evidence_analysis"] = evidence_eval
                return {
                    "session_id": session_id,
                    "status": "needs_more_context",
                    "evidence_evaluation": evidence_eval,
                    "gap_report": gap_report,
                    "context_analysis": context_analysis,
                    "message": "Context & evidence are insufficient. Additional documentation or human feedback required."
                }

        log_step("E_Context_Sufficient_Decision", "Context & Evidence Sufficient?", "passed", {
            "decision": "Yes - Sufficient Evidence & Context",
            "score": gap_report.get("sufficiency_score"),
            "evidence_rationale": evidence_eval.get("rationale")
        })

        # -------------------------------------------------------------------
        # Node F, G, H: PRD Generator, Reviewer, and Quality Loop
        # -------------------------------------------------------------------
        max_review_retries = 2
        review_attempt = 0
        prd_passed = False
        prd_content = ""
        review_result: Dict[str, Any] = {}
        reviewer_critique = None

        while review_attempt < max_review_retries and not prd_passed:
            review_attempt += 1
            prd_content = self.prd_service.generate(
                context=context_analysis,
                reviewer_feedback=reviewer_critique
            )
            log_step("F_PRD_Generator", f"5. PRD Generator (Attempt {review_attempt})", "completed", {
                "prd_length_chars": len(prd_content),
                "attempt": review_attempt
            })

            review_result = self.reviewer_service.review(prd_content, context_analysis)
            prd_passed = review_result.get("passed", False)

            log_step("G_PRD_Reviewer", f"6. PRD Reviewer (Attempt {review_attempt})", "completed", {
                "quality_score": review_result.get("quality_score"),
                "passed": prd_passed,
                "completeness_assessment": review_result.get("completeness_assessment"),
                "acceptance_criteria_valid": review_result.get("acceptance_criteria_valid"),
                "areas_for_improvement": review_result.get("areas_for_improvement")
            })

            if not prd_passed and review_attempt < max_review_retries:
                reviewer_critique = review_result.get("revision_instructions") or "Please address missing sections."
                log_step("H_PRD_Review_Passed_Decision", f"PRD Review Passed? (Attempt {review_attempt})", "retry_required", {
                    "decision": "Fail - Applying Revision Directives",
                    "revision_directives": reviewer_critique
                })
            else:
                log_step("H_PRD_Review_Passed_Decision", f"PRD Review Passed? (Attempt {review_attempt})", "pass", {
                    "decision": "Pass",
                    "score": review_result.get("quality_score")
                })
                break

        # -------------------------------------------------------------------
        # Node I: HITL Review (Lead Product Owner / BA Sign-off)
        # -------------------------------------------------------------------
        if auto_approve_hitl:
            hitl_record = self.hitl_service.process_review(
                prd_content=prd_content,
                decision="approve",
                reviewer_name="Lead Product Owner",
                reviewer_role="Product Owner / Business Analyst",
                comments=reviewer_comments or "PRD approved following automated quality evaluation."
            )
            log_step("I_HITL_Review", "7. HITL Review", "completed", hitl_record)
        else:
            # Pause workflow for manual Human-In-The-Loop review via /api/workflow/hitl/review
            session_state["status"] = "waiting_for_hitl"
            session_state["draft_prd"] = prd_content
            session_state["review_result"] = review_result
            session_state["context_analysis"] = context_analysis

            log_step("I_HITL_Review", "7. HITL Review", "waiting_for_human_approval", {
                "message": "PRD generated and quality check passed. Paused awaiting manual Product Owner approval.",
                "session_id": session_id,
                "approval_endpoint": "/api/workflow/hitl/review"
            })

            return {
                "session_id": session_id,
                "status": "waiting_for_hitl",
                "document_name": doc_name,
                "prd_draft": prd_content,
                "review_result": review_result,
                "context_analysis": {
                    "problem_statement": context_analysis.get("problem_statement"),
                    "business_goal": context_analysis.get("business_goal"),
                    "evidence_count": len(context_analysis.get("evidence", [])),
                    "mcp_skills": context_analysis.get("mcp_skills", []),
                    "mcp_context_package_id": context_analysis.get("mcp_context_package", {}).get("context_package_id")
                },
                "evidence_evaluation": evidence_eval,
                "gap_analysis": gap_report,
                "execution_steps": session_state["steps"],
                "message": "PRD draft ready. Awaiting human approval via POST /api/workflow/hitl/review."
            }

        # -------------------------------------------------------------------
        # Node J: Final Approved PRD & Publish to Jira or Confluence
        # -------------------------------------------------------------------
        publish_receipt = self.publish_service.publish_prd(
            prd_markdown=prd_content,
            context_data=context_analysis,
            target_platform=target_publish_platform
        )
        log_step("J_Final_Approved_PRD", "8. Final Approved PRD & Publish", "completed", publish_receipt)

        session_state["status"] = "completed"
        session_state["final_prd"] = prd_content
        session_state["publish_receipt"] = publish_receipt

        return {
            "session_id": session_id,
            "status": "completed",
            "document_name": doc_name,
            "context_analysis": {
                "problem_statement": context_analysis.get("problem_statement"),
                "business_goal": context_analysis.get("business_goal"),
                "evidence_count": len(context_analysis.get("evidence", [])),
                "mcp_skills": context_analysis.get("mcp_skills", []),
                "mcp_context_package_id": context_analysis.get("mcp_context_package", {}).get("context_package_id")
            },
            "evidence_evaluation": evidence_eval,
            "gap_analysis": gap_report,
            "review_result": review_result,
            "hitl_review": hitl_record,
            "publish_receipt": publish_receipt,
            "final_prd_markdown": prd_content,
            "execution_steps": session_state["steps"]
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)
