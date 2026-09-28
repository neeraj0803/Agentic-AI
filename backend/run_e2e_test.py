import json
from pathlib import Path
from src.services.workflow_service import WorkflowOrchestratorService


def run_test():
    print("==================================================")
    print("Running End-to-End Test with 21-Section Template")
    print("==================================================")

    sample_brd = Path("sample_data") / "cloud_cost_optimizer_brd.md"
    if not sample_brd.exists():
        print(f"Error: {sample_brd} not found!")
        return

    orchestrator = WorkflowOrchestratorService()

    print(f"\n1. Ingesting BRD: {sample_brd.name}")
    result = orchestrator.run_workflow_from_file(
        file_path=str(sample_brd),
        active_team_id="team-finops-cloud",
        target_publish_platform="both"
    )

    print(f"\n2. Workflow Execution Status: {result.get('status')}")
    print(f"   - Session ID: {result.get('session_id')}")
    print(f"   - Gap Analysis Sufficiency Score: {result.get('gap_analysis', {}).get('sufficiency_score')}")
    print(f"   - Review Passed: {result.get('review_result', {}).get('passed')}")
    print(f"   - Review Quality Score: {result.get('review_result', {}).get('quality_score')}")

    prd_md = result.get("final_prd_markdown", "")
    print(f"\n3. PRD Markdown Generated ({len(prd_md)} chars)")

    # Verify all 21 Roman numeral sections exist
    roman_sections = [
        "I. Problem Statement",
        "II. Impact of Problem",
        "III. Problem Area Process Map",
        "IV. What is Needed to Fix the Problem",
        "V. Customer and 3rd Party Research",
        "VI. Supporting Data",
        "VII. Solution Discovery, Recommendation, Teams Involved + Sizing",
        "VIII. Functional and Technical Design",
        "IX. To Be Process Map",
        "X. Impact Assessment / Opportunity / Metrics",
        "XI. Development Approach, High Level Requirements, + Epic Breakdown",
        "XII. Open Questions and Decision Log",
        "XIII. Roster",
        "XIV. Market Research",
        "XV. Competitive Analysis",
        "XVI. Target Personas",
        "XVII. Messaging & positioning",
        "XVIII. Pricing",
        "XIX. Distribution channels & launch activities",
        "XX. Support plan",
        "XXI. Reference materials"
    ]

    print("\n4. Verifying Presence of 21 PRD Sections:")
    all_found = True
    for sec in roman_sections:
        found = f"## {sec}" in prd_md or sec in prd_md
        status = "✅ Found" if found else "❌ MISSING"
        print(f"   [{status}] {sec}")
        if not found:
            all_found = False

    print("\n5. Checking Persistence Artifacts:")
    json_path = Path("prd_output.json")
    md_path = Path("prd_output.md")
    print(f"   - prd_output.json exists: {json_path.exists()} ({json_path.stat().st_size if json_path.exists() else 0} bytes)")
    print(f"   - prd_output.md exists: {md_path.exists()} ({md_path.stat().st_size if md_path.exists() else 0} bytes)")

    if all_found:
        print("\n🎉 SUCCESS: All 21 sections are present and validated!")
    else:
        print("\n⚠️ WARNING: Some sections were not matched.")

    print("\n--- PRD Preview (First 50 lines) ---")
    print("\n".join(prd_md.splitlines()[:50]))


if __name__ == "__main__":
    run_test()
