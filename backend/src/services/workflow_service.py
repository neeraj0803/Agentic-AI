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
from ..mcp import InProcessMCPClient
from ..agents.evidence_analyzer import evidence_analyzer_node
from ..config import settings


class WorkflowOrchestratorService:
    """
    End-to-End Workflow Orchestrator.
    Implements the flowchart (A -> B -> C -> D -> E -> F -> G -> H -> I -> J)
    and the 7-step Agent Journey.
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
        auto_approve_hitl: bool = False,
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
        # Node C: Context Analyzer (with Mock MCP Skill & Context)
        # Substeps 1, 2, 3: Classify intent, retrieve context, retrieve Jira/Confluence/Git
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
        # Node D & E: Gap Analyzer & Decision
        # Substep 4: Detect gaps, assumptions, and ambiguity
        # -------------------------------------------------------------------
        gap_report = self.gap_service.analyze_gaps(context_analysis)

        log_step("D_Gap_Analyzer", "3. Gap Analyzer", "completed", {
            "sufficiency_score": gap_report.get("sufficiency_score"),
            "is_sufficient": gap_report.get("is_sufficient", True),
            "gaps_count": len(gap_report.get("identified_gaps", [])),
            "conflicts_count": len(gap_report.get("detected_conflicts", [])),
            "conflicts": gap_report.get("detected_conflicts", []),
            "unvalidated_assumptions": gap_report.get("unvalidated_assumptions", [])
        })

        evidence_report = None

        if auto_approve_hitl:
            evidence_report = evidence_analyzer_node(context_analysis)
            is_sufficient = evidence_report["sufficient"]

            log_step(
                "E_Evidence_Analyzer",
                "Evidence Analyzer",
                "completed",
                evidence_report
            )
        else:
            # Preserve the existing gap-analyzer decision when HITL auto-approval is off.
            is_sufficient = gap_report.get("is_sufficient", True)

        if not is_sufficient and auto_approve_hitl:
            supplementary_path = r"D:\Agentic-AI\backend\sample_data\cloud_cost_optimizer_brd.md"

            log_step(
                "I_HITL_Context_Request",
                "Requesting supplementary context",
                "invoked",
                {
                    "missing_context": evidence_report.get("missing_context", []),
                    "weak_evidence": evidence_report.get("weak_evidence", []),
                    "rationale": evidence_report.get("rationale", ""),
                    "supplementary_file_configured": bool(supplementary_path),
                }
            )

            if not supplementary_path or not Path(supplementary_path).is_file():
                session_state["status"] = "waiting_for_hitl_context"
                session_state["context_analysis"] = context_analysis
                session_state["gap_report"] = gap_report
                session_state["evidence_analysis"] = evidence_report

                return {
                    "session_id": session_id,
                    "status": "needs_more_context",
                    "gap_report": gap_report,
                    "evidence_analysis": evidence_report,
                    "context_analysis": context_analysis,
                    "message": (
                        "Evidence is insufficient. HITL was invoked, but no valid "
                        "supplementary context file is configured."
                    ),
                }

            supplementary_text = DocumentExtractorService.extract_text(
                supplementary_path
            )
            combined_text = (
                f"{extracted_text}\n\n"
                "Additional context supplied during HITL review:\n"
                f"{supplementary_text}"
            )

            log_step(
                "I_HITL_Context_Request",
                "Supplementary context file read",
                "completed",
                {
                    "file_name": Path(supplementary_path).name,
                    "characters_extracted": len(supplementary_text),
                }
            )

            context_analysis = self.context_service.analyze(
                document_name=doc_name,
                extracted_text=combined_text,
                active_team_id=active_team_id,
                query_override=query_override,
            )
            log_step("C_Context_Analyzer", "2. Context Analyzer (HITL retry)", "completed", {
                "problem_statement": context_analysis.get("problem_statement"),
                "business_goal": context_analysis.get("business_goal"),
                "evidence_items": len(context_analysis.get("evidence", [])),
            })

            gap_report = self.gap_service.analyze_gaps(context_analysis)
            log_step("D_Gap_Analyzer", "3. Gap Analyzer (HITL retry)", "completed", {
                "sufficiency_score": gap_report.get("sufficiency_score"),
                "is_sufficient": gap_report.get("is_sufficient", True),
                "gaps_count": len(gap_report.get("identified_gaps", [])),
                "conflicts_count": len(gap_report.get("detected_conflicts", [])),
            })

            evidence_report = evidence_analyzer_node(context_analysis)
            is_sufficient = evidence_report["sufficient"]
            log_step(
                "E_Evidence_Analyzer",
                "Evidence Analyzer (HITL retry)",
                "completed",
                evidence_report
            )

        if not is_sufficient:
            log_step(
                "E_Context_Sufficient_Decision",
                "Context & Evidence Sufficient?",
                "failed_insufficient_evidence",
                {
                    "decision": "No - Missing Context / Weak Evidence",
                    "recommended_clarifications": gap_report.get(
                        "recommended_clarifications", []
                    ),
                    "evidence_analysis": evidence_report,
                }
            )
            session_state["status"] = "paused_missing_context"
            session_state["context_analysis"] = context_analysis
            session_state["gap_report"] = gap_report
            session_state["evidence_analysis"] = evidence_report

            return {
                "session_id": session_id,
                "status": "needs_more_context",
                "gap_report": gap_report,
                "evidence_analysis": evidence_report,
                "context_analysis": context_analysis,
                "message": (
                    "Context and evidence remain insufficient after HITL context "
                    "was analyzed."
                ),
            }

        log_step(
            "E_Context_Sufficient_Decision",
            "Context & Evidence Sufficient?",
            "passed",
            {
                "decision": "Yes - Sufficient Evidence & Context",
                "score": gap_report.get("sufficiency_score"),
                "evidence_analysis": evidence_report,
            }
        )

        # -------------------------------------------------------------------
        # Node F, G, H: PRD Generator, Reviewer, and Quality Loop
        # Substeps 5 & 6: Generate PRD draft & Run quality checks
        # -------------------------------------------------------------------
        max_review_retries = 2
        review_attempt = 0
        prd_passed = False
        prd_content = ""
        review_result: Dict[str, Any] = {}
        reviewer_critique = None

        while review_attempt < max_review_retries and not prd_passed:
            review_attempt += 1
            # Step 4: PRD Generator
            prd_content = self.prd_service.generate(
                context=context_analysis,
                reviewer_feedback=reviewer_critique
            )
            log_step("F_PRD_Generator", f"4. PRD Generator (Attempt {review_attempt})", "completed", {
                "prd_length": len(prd_content),
                "review_attempt": review_attempt
            })

            # Step 5: PRD Reviewer
            review_result = self.reviewer_service.review(prd_content, context_analysis)
            prd_passed = review_result.get("passed", False)

            log_step("G_PRD_Reviewer", f"5. PRD Reviewer (Attempt {review_attempt})", "completed", {
                "quality_score": review_result.get("quality_score"),
                "passed": prd_passed,
                "all_sections_present": review_result.get("completeness_assessment", {}).get("all_sections_present"),
                "areas_for_improvement": review_result.get("areas_for_improvement", [])
            })

            if not prd_passed:
                reviewer_critique = review_result.get("revision_instructions", "Add missing sections and acceptance criteria.")
                log_step("H_PRD_Review_Passed_Decision", f"PRD Review Passed? (Attempt {review_attempt})", "needs_improvement", {
                    "decision": "Needs Improvement",
                    "critique": reviewer_critique
                })
            else:
                log_step("H_PRD_Review_Passed_Decision", f"PRD Review Passed? (Attempt {review_attempt})", "pass", {
                    "decision": "Pass",
                    "score": review_result.get("quality_score")
                })
                break

        # -------------------------------------------------------------------
        # Node I: HITL Review (BA / Product Owner) - [COMMENTED OUT / BYPASSED]
        # -------------------------------------------------------------------
        # if auto_approve_hitl:
        #     hitl_record = self.hitl_service.process_review(
        #         prd_content=prd_content,
        #         decision="approve",
        #         reviewer_name="Lead Product Owner",
        #         reviewer_role="Product Owner / Business Analyst",
        #         comments=reviewer_comments or "Approved for release and Confluence/Jira publishing."
        #     )
        #     log_step("I_HITL_Review", "6. HITL Review", "approved", hitl_record)
        # else:
        #     # Pauses for manual human approval
        #     session_state["status"] = "waiting_for_hitl"
        #     session_state["draft_prd"] = prd_content
        #     session_state["review_result"] = review_result
        #     return {
        #         "session_id": session_id,
        #         "status": "waiting_for_hitl",
        #         "prd_draft": prd_content,
        #         "review_result": review_result,
        #         "message": "PRD review passed. Awaiting HITL approval from Product Owner."
        #     }
        hitl_record = {
            "status": "bypassed",
            "decision": "approve",
            "is_approved": True,
            "message": "HITL PO/Manager approval skipped. Auto-proceeding directly to publish."
        }
        log_step("I_HITL_Review", "6. HITL Review", "bypassed", hitl_record)

        # -------------------------------------------------------------------
        # Node J: Final Approved PRD & Publish to Jira or Confluence
        # Substep 7: Publish approved PRD
        # -------------------------------------------------------------------
        publish_receipt = self.publish_service.publish_prd(
            prd_markdown=prd_content,
            context_data=context_analysis,
            target_platform=target_publish_platform
        )
        log_step("J_Final_Approved_PRD", "7. Final Approved PRD & Publish", "completed", publish_receipt)

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
            "gap_analysis": gap_report,
            "review_result": review_result,
            "hitl_review": hitl_record,
            "publish_receipt": publish_receipt,
            "final_prd_markdown": prd_content,
            "execution_steps": session_state["steps"]
        }

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)

