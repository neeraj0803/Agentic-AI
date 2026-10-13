import datetime
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_ac_points(ac_text: str | None) -> list[str]:
    """Splits acceptance criteria text into individual bullet points/criteria."""
    if not ac_text:
        return []
    lines = ac_text.strip().splitlines()
    points = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"^[-*•\d.]+\s*", "", cleaned)
        if cleaned:
            points.append(cleaned)
    return points


def analyze_architectural_signals(ac_points: list[str], scope: str) -> list[str]:
    """Surfaces domain & architectural signals from AC and scope."""
    signals = []
    full_text = " ".join(ac_points).lower()

    # Latency / Performance signals
    if any(k in full_text for k in ["latency", "p95", "p99", "concurrency", "load", "requests/sec"]):
        signals.append("NFR - Latency & Throughput SLA requirements identified")
    
    # Boundary & Edge signals
    if any(k in full_text for k in ["boundary", "edge case", "exceed", "max", "null", "empty"]):
        signals.append("Boundary Conditions - Extreme input sizes and empty/null boundary checks needed")

    # Security & Data Privacy signals
    if any(k in full_text for k in ["pii", "passport", "ssn", "masking", "phone number", "auth", "token"]):
        signals.append("Security & Compliance - PII data masking and sensitive field validation required")

    # Fault Tolerance & Downstream Resilience signals
    if any(k in full_text for k in ["resilience", "downstream", "timeout", "500", "fail-open", "fail-closed", "retry"]):
        signals.append("Resilience - Downstream dependency failure handling, circuit breaking, and timeout policies")

    # Error handling & Rate Limiting signals
    if any(k in full_text for k in ["429", "rate limit", "exponential backoff", "malformed"]):
        signals.append("Resilience - Rate limit backoff (HTTP 429) and malformed payload reporting")

    if not signals:
        signals.append(f"Standard {scope.replace('_', ' ').title()} architectural verification scope")

    return signals


def analyze_risk_factors(ac_points: list[str], scope: str) -> list[dict[str, str]]:
    """Identifies test risk surfaces and suggested mitigations."""
    risks = []
    full_text = " ".join(ac_points).lower()

    if "pii" in full_text or "mask" in full_text:
        risks.append({
            "category": "Data Security & Compliance",
            "risk": "Unmasked PII leakage into application logs or downstream events.",
            "mitigation": "Execute comprehensive boundary and negative test suites across all phone, passport, and SSN formats.",
        })

    if "latency" in full_text or "500" in full_text or "timeout" in full_text:
        risks.append({
            "category": "System Availability & Performance",
            "risk": "Downstream classifier timeout leading to cascading service disruption or unhandled 500 errors.",
            "mitigation": "Simulate mock network latency (>100ms) and confirm fail-open/fail-closed policy triggers accurately.",
        })

    if "malformed" in full_text or "jsonl" in full_text:
        risks.append({
            "category": "Data Ingestion Integrity",
            "risk": "Corrupt or malformed input crashing batch worker or evaluation loop.",
            "mitigation": "Validate schema rejection and line-numbered diagnostic logging for corrupt datasets.",
        })

    if not risks:
        risks.append({
            "category": "Functional Regression",
            "risk": "Regression impact on existing modules.",
            "mitigation": "Run regression and boundary validation suites.",
        })

    return risks


def execute(state: dict[str, Any], parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Context Brief Generator skill execution.
    
    Synthesizes input context and Jira requirements into a structured
    Context Brief for downstream test case drafting.
    """
    params = parameters or {}
    logger.info("Executing Context Brief Generator skill with params: %s", params)

    validated_inputs = state.get("validated_inputs", {})
    context_data = state.get("input_context") or state.get("context_data", {})

    story_id = (
        validated_inputs.get("jira_story_or_epic_id")
        or (context_data[0].get("jira_story_or_epic_id") if isinstance(context_data, list) and context_data else "N/A")
    )
    raw_ac = validated_inputs.get("acceptance_criteria")
    if raw_ac is None and isinstance(context_data, list) and context_data:
        raw_ac = context_data[0].get("acceptance_criteria")

    ac_text = str(raw_ac or "")
    scope = validated_inputs.get("test_scope_and_type") or "functional_and_negative"
    target_env = validated_inputs.get("target_application_and_env") or "auto_resolve_from_jira"
    output_pref = validated_inputs.get("output_preference") or "xray_record"

    ac_points = extract_ac_points(ac_text)
    architectural_signals = analyze_architectural_signals(ac_points, scope)
    risk_factors = analyze_risk_factors(ac_points, scope)

    summary = (
        f"Context brief for story {story_id} targeting '{target_env}' with scope '{scope}'. "
        f"Identified {len(ac_points)} acceptance criteria items, {len(architectural_signals)} key architectural signals, "
        f"and {len(risk_factors)} prioritized risk factors for manual and automated test drafting."
    )

    brief = {
        "status": "completed",
        "skill": "context_brief_generator",
        "version": "1.5",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "story_id": story_id,
        "target_application_and_env": target_env,
        "test_scope_and_type": scope,
        "output_preference": output_pref,
        "acceptance_criteria_items": ac_points,
        "architectural_signals": architectural_signals,
        "risk_analysis": risk_factors,
        "recommended_focus": [
            f"Prioritize {scope.replace('_', ' ')} scenarios with explicit negative and boundary testing",
            "Verify graceful error degradation and timeout boundaries on downstream integrations",
            "Ensure bi-directional traceability against all specified acceptance criteria",
        ],
        "summary": summary,
    }

    return brief


# Export common aliases for dynamic invokers
run = execute
context_brief_generator = execute

