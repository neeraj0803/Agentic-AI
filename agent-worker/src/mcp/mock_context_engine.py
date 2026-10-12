import re
import uuid
from typing import Any, Dict, List
from .schemas import JsonRpcRequest, JsonRpcResponse


class MockContextEngine:
    """
    In-process Mock MCP Context Engine (Prism Context Engine).
    Handles `tools/call` for `prism.context.retrieve` conforming strictly to the JSON-RPC 2.0 schema.
    Dynamically analyzes query and scope parameters to retrieve domain-relevant Jira, Confluence,
    and Git references, candidate signals, gaps, and conflicts without hardcoding a single static output.
    """

    def handle_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request_payload.get("id", f"ctx-req-{uuid.uuid4().hex[:6]}")
        params = request_payload.get("params", {})
        args = params.get("arguments", {})
        query_dict = args.get("query", {})
        query_text = query_dict.get("text", "Enterprise capability requirements")
        scope = args.get("apex_scope", {})
        team_id = scope.get("active_team_id", "team-enterprise-product")

        # Dynamically infer domain, entity names, and project keys from query & scope
        context_package = self._build_dynamic_context_package(query_text, team_id, scope)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tool": "prism.context.retrieve",
                "status": "partial",
                "context_package": context_package
            }
        }

    def _build_dynamic_context_package(
        self,
        query_text: str,
        team_id: str,
        scope: Dict[str, Any]
    ) -> Dict[str, Any]:
        q_lower = query_text.lower()
        package_id = f"ctx-pkg-{uuid.uuid4().hex[:8]}"

        if any(w in q_lower for w in ["kyc", "identity", "onboard", "verification", "passport", "biometric"]):
            domain_name = "Identity & Verification"
            app_name = "Identity Verification Service"
            repo_name = "identity-service"
            project_key = "IDV"
            space_key = "IDENTITY"
            change_summary = "Automate user onboarding and identity verification workflows."
            capabilities = ["identity verification", "document OCR", "fraud screening"]
            epic_summary = "Improve digital customer onboarding throughput with automated KYC"
            code_file = "src/verification/DocumentVerificationEngine.java"
            code_snippet = "verifyGovernmentId(documentBytes, customerId)"
            domain_doc_title = "Global KYC & Anti-Money Laundering Compliance Guidelines"
            domain_doc_snippet = "User verification must complete within 60 seconds with 99.5% accuracy."
            prior_prd_title = "Customer Identity Management Architecture"
            prior_prd_snippet = "Identity data must be encrypted with AES-256 and audited per regulatory standards."
            gaps = [
                "Need confirmation on supported national ID types for international expansion.",
                "Need clarity on acceptable fallback flow when OCR confidence is below 85%."
            ]
            conflicts = []
        elif any(w in q_lower for w in ["fulfillment", "tracking", "shipment", "delivery", "order", "logistics"]):
            domain_name = "Logistics & Fulfillment"
            app_name = "Order Tracking Service"
            repo_name = "order-tracking-service"
            project_key = "ORD"
            space_key = "LOGISTICS"
            change_summary = "Real-time shipment milestone notifications and delivery tracking."
            capabilities = ["order tracking", "carrier webhook ingestion", "event notification"]
            epic_summary = "Provide real-time shipment status updates and carrier milestone alerts"
            code_file = "src/tracking/CarrierWebhookDispatcher.java"
            code_snippet = "processCarrierStatusUpdate(carrierPayload)"
            domain_doc_title = "Logistics Carrier Integration & Webhook Standards"
            domain_doc_snippet = "Carrier webhook updates must be processed asynchronously via Kafka within 500ms."
            prior_prd_title = "Order Management System v1.2 PRD"
            prior_prd_snippet = "Order state updates must emit domain events to downstream consumer notifications."
            gaps = [
                "Need confirmation of carrier partner SLA and webhook timeout thresholds.",
                "Need target delivery date prediction accuracy metric."
            ]
            conflicts = []
        elif any(w in q_lower for w in ["cloud", "cost", "finops", "optimizer", "aws", "azure", "kubernetes", "infra"]):
            domain_name = "Cloud Infrastructure & FinOps"
            app_name = "Cloud Cost Management Service"
            repo_name = "cloud-cost-optimizer"
            project_key = "OPS"
            space_key = "FINOPS"
            change_summary = "Automated cloud resource rightsizing and cost anomaly detection."
            capabilities = ["cost anomaly detection", "resource rightsizing", "budget alerting"]
            epic_summary = "Implement automated idle resource termination and rightsizing recommendations"
            code_file = "src/finops/ResourceUsageAnalyzer.py"
            code_snippet = "evaluateIdleResources(cluster_metrics, threshold_days=7)"
            domain_doc_title = "Enterprise Cloud Governance & FinOps Guidelines"
            domain_doc_snippet = "Non-production clusters must have scheduled scale-down during off-peak hours."
            prior_prd_title = "Infrastructure Observability & Cost Tracking PRD"
            prior_prd_snippet = "All cloud workloads must carry mandatory cost-center and owner tags."
            gaps = [
                "Need confirmation whether auto-remediation requires manual ops team approval.",
                "Need target monthly cloud spend reduction target percentage."
            ]
            conflicts = []
        elif any(w in q_lower for w in ["payment", "retry", "checkout", "declined"]):
            domain_name = "Checkout"
            app_name = "Checkout Service"
            repo_name = "checkout-service"
            project_key = "CHK"
            space_key = "CHECKOUT"
            change_summary = "Improve payment retry messaging in checkout."
            capabilities = ["checkout payment", "payment retry"]
            epic_summary = "Improve checkout payment recovery journey"
            code_file = "src/payment/PaymentErrorMapper.java"
            code_snippet = "mapRecoverablePaymentFailure(errorCode)"
            domain_doc_title = "Checkout Payment Experience Standards"
            domain_doc_snippet = "Payment error messages should distinguish retryable and non-retryable failures."
            prior_prd_title = "Checkout Payment Resilience PRD"
            prior_prd_snippet = "Customers should receive recoverable payment guidance when authorization failures occur."
            gaps = [
                "Need confirmation of target payment methods and markets.",
                "Need target metric for abandonment or retry success improvement."
            ]
            conflicts = [
                {
                    "conflict_id": "conflict-prd-001",
                    "description": "Older PRD excludes retry messaging; current epic includes it.",
                    "references": ["ref-prd-001", "ref-prd-002"]
                }
            ]
        elif any(w in q_lower for w in ["conflict", "contradict", "manual review"]):
            domain_name = "Transaction Processing"
            app_name = "Transaction Routing Service"
            repo_name = "transaction-router"
            project_key = "TXN"
            space_key = "FINANCE"
            change_summary = "Automated transaction routing with regulatory inspection constraints."
            capabilities = ["transaction processing", "risk evaluation", "compliance screening"]
            epic_summary = "Automate high-volume transaction straight-through processing"
            code_file = "src/routing/TransactionProcessor.java"
            code_snippet = "routeTransactionStraightThrough(txn)"
            domain_doc_title = "Transaction Compliance & Inspection Mandates"
            domain_doc_snippet = "Mandatory compliance review required for high-risk foreign currency settlements."
            prior_prd_title = "Transaction Routing System PRD"
            prior_prd_snippet = "Straight-through automated processing without manual intervention."
            gaps = ["Need resolution on conflicting automated straight-through vs 100% manual review mandate."]
            conflicts = [
                {
                    "conflict_id": "conflict-txn-001",
                    "description": "Business objective aims for 100% automated straight-through processing, while compliance standard requires manual review for every transaction.",
                    "references": ["ref-prior-prd", "ref-domain-doc"]
                }
            ]
        else:
            clean_subject = re.sub(r"[^a-zA-Z0-9\s]", "", query_text).strip()
            title_words = [w.capitalize() for w in clean_subject.split() if len(w) > 2][:4]
            short_name = " ".join(title_words) or "Core System"
            key_code = "".join([w[0].upper() for w in title_words[:3]]) or "ENG"

            domain_name = f"{short_name} Domain"
            app_name = f"{short_name} Service"
            repo_name = short_name.lower().replace(" ", "-") + "-service"
            project_key = key_code
            space_key = key_code
            change_summary = f"Implement capabilities for {query_text}."
            capabilities = [f"{short_name.lower()} management", "core processing", "event ingestion"]
            epic_summary = f"Deliver {short_name} capability enhancements"
            code_file = f"src/core/{short_name.replace(' ', '')}Manager.java"
            code_snippet = f"execute{short_name.replace(' ', '')}Workflow(requestContext)"
            domain_doc_title = f"{short_name} Architecture and API Standards"
            domain_doc_snippet = f"All {short_name} APIs must be RESTful and return responses within 100ms."
            prior_prd_title = f"{short_name} Foundation PRD"
            prior_prd_snippet = f"Baseline architecture and data modeling for {short_name}."
            gaps = [f"Need confirmation of target volume and latency SLAs for {short_name}."]
            conflicts = []

        return {
            "context_package_id": package_id,
            "query_interpretation": {
                "intent": "prd_context_generation",
                "change_summary": change_summary,
                "detected_entities": {
                    "business_capabilities": capabilities,
                    "applications": [app_name],
                    "source_families": ["jira", "confluence", "git"]
                }
            },
            "retrieved_references": [
                {
                    "reference_id": "ref-prd-001",
                    "source_type": "prior_prd",
                    "title": prior_prd_title,
                    "relevance": "high",
                    "reason_for_relevance": f"Prior architecture baseline for {domain_name}.",
                    "snippet": prior_prd_snippet,
                    "link": f"https://confluence.corp.internal/display/{space_key}/{prior_prd_title.replace(' ', '+')}"
                },
                {
                    "reference_id": "ref-prd-002",
                    "source_type": "jira_epic",
                    "source_id": f"{project_key}-100",
                    "title": epic_summary,
                    "relevance": "high",
                    "reason_for_relevance": "Active business initiative in Jira.",
                    "snippet": f"Objective: {epic_summary}.",
                    "link": f"https://jira.corp.internal/browse/{project_key}-100"
                },
                {
                    "reference_id": "ref-prd-003",
                    "source_type": "domain_doc",
                    "title": domain_doc_title,
                    "relevance": "medium",
                    "reason_for_relevance": "Enterprise domain architecture policy and standards.",
                    "snippet": domain_doc_snippet,
                    "link": f"https://confluence.corp.internal/display/{space_key}/Standards"
                },
                {
                    "reference_id": "ref-prd-004",
                    "source_type": "code_reference",
                    "repository": repo_name,
                    "file_path": code_file,
                    "relevance": "medium",
                    "reason_for_relevance": "Core domain code handler in Git.",
                    "snippet": code_snippet,
                    "link": f"https://git.corp.internal/{repo_name}/blob/main/{code_file}"
                }
            ],
            "candidate_signals": {
                "business_goals": [
                    f"Improve throughput and operational efficiency in {domain_name}",
                    "Reduce manual intervention and customer wait time"
                ],
                "possible_prd_sections": [
                    "problem statement",
                    "goals",
                    "non-goals",
                    "user journey",
                    "scope",
                    "dependencies",
                    "risks",
                    "open questions"
                ],
                "likely_impacted_capabilities": capabilities
            },
            "gaps_or_questions": gaps,
            "conflicts": conflicts,
            "permission_exclusions": [],
            "freshness": {
                "jira": "indexed_10_minutes_ago",
                "confluence": "indexed_1_hour_ago",
                "git": "indexed_30_minutes_ago"
            },
            "package_metadata": {
                "references_returned": 4,
                "references_considered": 48,
                "estimated_tokens": 5800,
                "budget_target": "medium",
                "ranking_method": "semantic_plus_artifact_links"
            }
        }
