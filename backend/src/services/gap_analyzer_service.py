from typing import Any, Dict
from ..agents.gap_analyzer import GapAnalyzerPrompt


class GapAnalyzerService:
    """
    Evaluates context quality, evidence sufficiency, and conflict detection.
    Corresponds to Step 4 (Detect gaps, assumptions & ambiguity) in Agent Journey
    and Decision E (Context & Evidence Sufficient?) in flowchart.md.
    """

    def analyze_gaps(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        return GapAnalyzerPrompt.analyze(context_data)

