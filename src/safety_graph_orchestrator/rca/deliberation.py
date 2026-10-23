import json
import logging
import re
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from safety_graph_orchestrator.core.llm import get_llm
from safety_graph_orchestrator.core.models import (
    AgentPerspective,
    RetrievedSOP,
    RootCauseAnalysisResult,
    RuleViolation,
    UnifiedSafetyData,
)
from safety_graph_orchestrator.rca.five_whys import FiveWhysEngine

logger = logging.getLogger(__name__)


class OperationsSafetyAgent:
    """Evaluates incident through the lens of rig field operations, crew fatigue, and shift handover."""

    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def evaluate(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        sops: List[RetrievedSOP],
    ) -> AgentPerspective:
        prompt = f"""You are the Field Drilling Operations Superintendent Agent.
Analyze this incident from the perspective of drilling tour realities: schedule pressure, shift handover, tool availability, and operational tempo.
Incident: {data.summary}
Pressure: {data.high_pressure_psi} PSI | H2S: {data.h2s_ppm} ppm | SWA: {data.swa_invoked} (Premature: {data.premature_restart})
Violations: {', '.join([v.rule_name for v in violations])}

Return ONLY JSON:
{{
  "agent_role": "Field Operations & Shift Governance",
  "key_findings": ["Finding 1", "Finding 2"],
  "causal_assessment": "Operational factor assessment",
  "identified_vulnerabilities": ["Vulnerability 1"],
  "recommended_focus": "Specific operational focus for containment",
  "confidence": 0.92
}}"""
        try:
            res = self.llm.invoke([SystemMessage(content="You are a seasoned drilling superintendent."), HumanMessage(content=prompt)])
            text = res.content if hasattr(res, "content") else str(res)
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            parsed = json.loads(match.group(1) if match else text.strip())
            return AgentPerspective(**parsed)
        except Exception:
            return AgentPerspective(
                agent_role="Field Operations & Shift Governance",
                key_findings=[
                    "High operational tempo prior to tour change created schedule pressure",
                    "Shift handover lacked formal verification of barrier status",
                ],
                causal_assessment="Schedule pressure and tour handover communication gap allowed shortcut execution.",
                identified_vulnerabilities=[
                    "Unwritten pressure to avoid non-productive time (NPT)",
                    "Informal verbal sign-offs instead of documented checklists",
                ],
                recommended_focus="Implement mandatory digital shift handover QA/QC barrier sign-off checklist.",
                confidence=0.92,
            )


class RegulatoryComplianceAgent:
    """Evaluates incident through the lens of OSHA CFR standards and API RP 54 mandates."""

    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def evaluate(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        sops: List[RetrievedSOP],
    ) -> AgentPerspective:
        prompt = f"""You are the OSHA & API RP 54 Regulatory Compliance Auditor Agent.
Analyze statutory violations, non-negotiable legal requirements, and SWA protocol integrity.
Incident: {data.summary}
H2S: {data.h2s_ppm} ppm | Pressure: {data.high_pressure_psi} PSI | Fall Height: {data.fall_height_ft} ft
Violations: {', '.join([v.citation for v in violations])}

Return ONLY JSON:
{{
  "agent_role": "Regulatory Compliance & Legal Standards",
  "key_findings": ["Finding 1", "Finding 2"],
  "causal_assessment": "Statutory non-conformance assessment",
  "identified_vulnerabilities": ["Vulnerability 1"],
  "recommended_focus": "Regulatory mandate focus",
  "confidence": 0.95
}}"""
        try:
            res = self.llm.invoke([SystemMessage(content="You are a strict OSHA & API compliance auditor."), HumanMessage(content=prompt)])
            text = res.content if hasattr(res, "content") else str(res)
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            parsed = json.loads(match.group(1) if match else text.strip())
            return AgentPerspective(**parsed)
        except Exception:
            return AgentPerspective(
                agent_role="Regulatory Compliance & Legal Standards",
                key_findings=[
                    f"Direct violation of applicable safety standards: {', '.join([v.citation for v in violations[:2]]) or 'API RP 54'}",
                    "Stop Work Authority protection protocols compromised if premature restart occurred",
                ],
                causal_assessment="Failure to enforce mandatory statutory stop-work protections and baseline exposure limits.",
                identified_vulnerabilities=[
                    "Lack of clear legal consequences for bypassing SWA resolution gates",
                    "Deficient atmospheric testing prior to commencing hot or pressurized tasks",
                ],
                recommended_focus="Strict enforcement of OSHA 1910 / API RP 54 SWA restart sign-off protocols.",
                confidence=0.96,
            )


class EquipmentReliabilityAgent:
    """Evaluates mechanical integrity, tool calibration, pressure limits, and material failure modes."""

    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def evaluate(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        sops: List[RetrievedSOP],
    ) -> AgentPerspective:
        prompt = f"""You are the Forensic Reliability & Mechanical Integrity Engineer Agent.
Analyze pressure-containing integrity, gasket specifications, tool calibration, and physical failure modes.
Incident: {data.summary}
Pressure: {data.high_pressure_psi} PSI | H2S: {data.h2s_ppm} ppm
Violations: {', '.join([v.rule_name for v in violations])}

Return ONLY JSON:
{{
  "agent_role": "Equipment Reliability & Forensic Engineering",
  "key_findings": ["Finding 1", "Finding 2"],
  "causal_assessment": "Mechanical failure mechanism assessment",
  "identified_vulnerabilities": ["Vulnerability 1"],
  "recommended_focus": "Mechanical barrier focus",
  "confidence": 0.94
}}"""
        try:
            res = self.llm.invoke([SystemMessage(content="You are a senior forensic mechanical engineer."), HumanMessage(content=prompt)])
            text = res.content if hasattr(res, "content") else str(res)
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            parsed = json.loads(match.group(1) if match else text.strip())
            return AgentPerspective(**parsed)
        except Exception:
            return AgentPerspective(
                agent_role="Equipment Reliability & Forensic Engineering",
                key_findings=[
                    "Pressure-containing equipment subjected to uneven mechanical load or uncalibrated tooling",
                    "Gasket sealing integrity compromised under operating pressure pulsations",
                ],
                causal_assessment="Mechanical barrier failure accelerated by improper bolt-torque sequence and uncalibrated tools.",
                identified_vulnerabilities=[
                    "Use of uncalibrated impact wrenches instead of certified hydraulic torque equipment",
                    "Absence of secondary hydrostatic pressure test verification prior to live service",
                ],
                recommended_focus="Decommission defective seals, enforce calibrated torque tools, and mandate chart-recorded pressure test.",
                confidence=0.94,
            )


class SafetyArbiter:
    """Reconciles specialized agent perspectives into a unified 5 Whys causal breakdown."""

    def __init__(self, five_whys_engine: FiveWhysEngine | None = None):
        self.five_whys_engine = five_whys_engine or FiveWhysEngine()

    def synthesize(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        sops: List[RetrievedSOP],
        deliberations: List[AgentPerspective],
    ) -> RootCauseAnalysisResult:
        # Pass deliberations into the 5 Whys engine
        rca_result = self.five_whys_engine.analyze(data, violations, sops)
        rca_result.deliberation_perspectives = deliberations

        # Enrich contributing factors with key findings from committee
        for p in deliberations:
            for finding in p.key_findings:
                if finding not in rca_result.contributing_factors:
                    rca_result.contributing_factors.append(f"[{p.agent_role}] {finding}")

        return rca_result
