import json
import logging
import re
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from safety_graph_orchestrator.core.llm import get_llm
from safety_graph_orchestrator.core.models import (
    FiveWhysStep,
    RetrievedSOP,
    RootCauseAnalysisResult,
    RootCauseCategory,
    RuleViolation,
    UnifiedSafetyData,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite Root Cause Analysis (RCA) expert in hazardous industrial and drilling operations.
You utilize the structured "5 Whys" methodology to drill down from physical symptoms to systemic, organizational root causes.
Do not blame individuals; identify latent management system weaknesses, training gaps, tool availability, and procedural deficiencies.

Return ONLY a valid JSON object matching this schema:
{
  "incident_summary": "Concise summary of the event",
  "direct_cause": "The immediate physical condition or failure",
  "contributing_factors": ["Factor 1", "Factor 2"],
  "five_whys": [
    {
      "level": 1,
      "question": "Why did [physical event] occur?",
      "answer": "[Immediate operational/mechanical cause]",
      "causal_category": "Equipment Integrity & Mechanical Failure" | "Human Factors (Situational Awareness / Fatigue)" | "Procedural Adherence & SOP Gap" | "Management Systems & Resource Allocation" | "Communication & Shift Handover Gap" | "Inadequate Pre-job Hazard Identification",
      "confidence_score": 0.95
    },
    ... (all 5 levels required)
  ],
  "root_cause_statement": "Definitive organizational/systemic root cause statement",
  "primary_category": "Management Systems & Resource Allocation",
  "systemic_failure_pattern": "Summary of systemic flaw"
}
"""


class FiveWhysEngine:
    """Orchestrates 5 Whys Root Cause Analysis via Ollama or structured fallback."""

    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def analyze(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        sops: List[RetrievedSOP],
    ) -> RootCauseAnalysisResult:
        prompt = self._build_prompt(data, violations, sops)

        try:
            response = self.llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            content = response.content if hasattr(response, "content") else str(response)
            result = self._parse_response(content, data)
            if result:
                return result
        except Exception as e:
            logger.warning("LLM 5 Whys generation encountered error: %s. Applying heuristic fallback.", e)

        return self._heuristic_fallback(data, violations, sops)

    def _build_prompt(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        sops: List[RetrievedSOP],
    ) -> str:
        violations_summary = "\n".join([f"- [{v.severity}] {v.rule_name}: {v.description}" for v in violations]) or "None"
        sops_summary = "\n".join([f"- {s.doc_id} ({s.title}): {s.content[:150]}..." for s in sops]) or "None"

        return f"""Perform a rigorous 5 Whys Root Cause Analysis on the following operational safety incident:

Rig / Asset ID: {data.rig_id}
Document Type: {data.input_type}
Timestamp: {data.timestamp}
Operational Summary: {data.summary}

Reported Parameters:
- Operating Pressure: {data.high_pressure_psi} PSI
- H2S Level: {data.h2s_ppm} ppm
- LEL Level: {data.lel_pct}%
- Fall Height: {data.fall_height_ft} ft
- SWA Invoked: {data.swa_invoked} (Premature Restart: {data.premature_restart})
- Hot Work Active: {data.hot_work_active}

Identified Safety Rule Violations:
{violations_summary}

Relevant Standard Operating Procedures & Regulations:
{sops_summary}

Raw Report Details:
{data.raw_text[:1200]}

Analyze the root causes using 5 Whys and return strictly JSON."""

    def _parse_response(self, text: str, data: UnifiedSafetyData) -> Optional[RootCauseAnalysisResult]:
        # Extract JSON from potential code fences
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        json_str = match.group(1) if match else text.strip()

        # Try direct parse
        try:
            parsed = json.loads(json_str)
            five_whys_list = []
            for item in parsed.get("five_whys", []):
                cat_str = item.get("causal_category", RootCauseCategory.PROCEDURAL_COMPLIANCE.value)
                category = self._match_category(cat_str)
                five_whys_list.append(
                    FiveWhysStep(
                        level=int(item.get("level", len(five_whys_list) + 1)),
                        question=item.get("question", ""),
                        answer=item.get("answer", ""),
                        causal_category=category,
                        confidence_score=float(item.get("confidence_score", 0.9)),
                    )
                )

            primary_cat_str = parsed.get("primary_category", RootCauseCategory.MANAGEMENT_SYSTEMS.value)
            primary_cat = self._match_category(primary_cat_str)

            return RootCauseAnalysisResult(
                incident_summary=parsed.get("incident_summary", data.summary),
                direct_cause=parsed.get("direct_cause", "Physical barrier compromise or procedural variance"),
                contributing_factors=parsed.get("contributing_factors", []),
                five_whys=five_whys_list,
                root_cause_statement=parsed.get("root_cause_statement", "Systemic management and verification gap"),
                primary_category=primary_cat,
                systemic_failure_pattern=parsed.get("systemic_failure_pattern", "Organizational pressure overriding safety barrier verification"),
            )
        except Exception as e:
            logger.debug("Failed to parse JSON response: %s", e)
            return None

    def _match_category(self, cat_str: str) -> RootCauseCategory:
        for member in RootCauseCategory:
            if member.name.lower() in cat_str.lower() or member.value.lower() in cat_str.lower():
                return member
        return RootCauseCategory.MANAGEMENT_SYSTEMS

    def _heuristic_fallback(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        sops: List[RetrievedSOP],
    ) -> RootCauseAnalysisResult:
        """Deterministic 5 Whys reasoning chain when LLM is unavailable."""
        sop_ref = sops[0].doc_id if sops else "SOP-042"
        v_title = violations[0].rule_name if violations else "Operational Safety Breach"

        steps = [
            FiveWhysStep(
                level=1,
                question=f"Why was an unsafe condition ({v_title}) observed on {data.rig_id}?",
                answer=f"Physical barriers or operating limits were exceeded without immediate containment ({data.summary}).",
                causal_category=RootCauseCategory.EQUIPMENT_INTEGRITY if data.high_pressure_psi > 0 else RootCauseCategory.HUMAN_FACTORS,
                confidence_score=0.95,
            ),
            FiveWhysStep(
                level=2,
                question="Why were operating barriers not maintained within specification?",
                answer=f"Pre-task execution deviated from the requirements detailed in {sop_ref}.",
                causal_category=RootCauseCategory.PROCEDURAL_COMPLIANCE,
                confidence_score=0.92,
            ),
            FiveWhysStep(
                level=3,
                question=f"Why was {sop_ref} not fully implemented prior to commencing the task?",
                answer="Shift crew lacked calibrated verification tools and rushed execution to meet tour handover targets.",
                causal_category=RootCauseCategory.PROCEDURAL_COMPLIANCE,
                confidence_score=0.90,
            ),
            FiveWhysStep(
                level=4,
                question="Why were unverified conditions permitted to proceed without supervisory intervention?",
                answer="The supervisory sign-off checklist and Stop Work Authority verification gate were treated as administrative formalities.",
                causal_category=RootCauseCategory.COMMUNICATION_HANDOVER,
                confidence_score=0.88,
            ),
            FiveWhysStep(
                level=5,
                question="Why did safety management systems fail to enforce procedural compliance?",
                answer="Management systems prioritized operational uptime over secondary barrier verification, creating latent organizational tolerance for procedural drift.",
                causal_category=RootCauseCategory.MANAGEMENT_SYSTEMS,
                confidence_score=0.94,
            ),
        ]

        return RootCauseAnalysisResult(
            incident_summary=f"Incident on Rig {data.rig_id}: {data.summary}",
            direct_cause="Immediate failure of operational safety barrier and procedural non-conformance.",
            contributing_factors=[
                "Inadequate shift handover verification",
                "Pressure to maintain drilling schedule",
                "Deficient secondary barrier testing",
            ],
            five_whys=steps,
            root_cause_statement=(
                "Latent organizational failure to mandate independent supervisory verification of critical safety barriers, "
                "leading to normalized procedural deviance under operational schedule pressures."
            ),
            primary_category=RootCauseCategory.MANAGEMENT_SYSTEMS,
            systemic_failure_pattern="Operational pace superseding rigorous compliance verification.",
        )
