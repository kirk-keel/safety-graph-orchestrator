from datetime import datetime, timezone
import json
import logging
import re
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from safety_graph_orchestrator.core.llm import get_llm
from safety_graph_orchestrator.core.models import (
    AuditStatus,
    CAPAItem,
    CorrectiveActionReport,
    RetrievedSOP,
    RootCauseAnalysisResult,
    RuleViolation,
    SeverityLevel,
    UnifiedSafetyData,
)

logger = logging.getLogger(__name__)

CAR_SYSTEM_PROMPT = """You are an enterprise Health, Safety, and Environment (HSE) Compliance Director in oil & gas and industrial manufacturing.
You generate formal, audit-ready Corrective Action Reports (CAR / CAPA) adhering to API Q2, ISO 45001, and OSHA standards.
Your output must be concise, authoritative, and actionable.

Return ONLY a valid JSON object matching this schema:
{
  "car_number": "CAR-2026-XXXX",
  "executive_summary": "High-level audit narrative detailing non-conformances and risk to operations",
  "action_items": [
    {
      "action_id": "CAPA-01",
      "action_type": "CONTAINMENT" | "CORRECTIVE" | "PREVENTIVE",
      "description": "Specific, actionable engineering or administrative action",
      "responsible_party": "e.g. Rig Superintendent, HSE Lead, Toolpusher",
      "target_completion_days": 1,
      "regulatory_mandate": "Citation",
      "verification_method": "Documented evidence required to close action"
    }
  ]
}
"""


class CARGenerator:
    """Generates Corrective Action Reports (CAR) and CAPA action items."""

    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def generate(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        rca: Optional[RootCauseAnalysisResult],
        sops: List[RetrievedSOP],
    ) -> CorrectiveActionReport:
        # Determine overall severity
        overall_severity = self._compute_overall_severity(violations)
        requires_director_signoff = overall_severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
        osha_reportable = overall_severity == SeverityLevel.CRITICAL and (data.h2s_ppm >= 20.0 or data.premature_restart)

        citations = list(set([v.citation for v in violations] + [s.standard_reference for s in sops]))
        referenced_sops = [f"{s.doc_id}: {s.title}" for s in sops]

        llm_output = self._call_llm_for_capa(data, violations, rca, sops, overall_severity)

        car_number = llm_output.get("car_number", f"CAR-{data.rig_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}")
        exec_summary = llm_output.get("executive_summary") or self._generate_default_summary(data, violations, overall_severity)
        actions = self._build_action_items(llm_output.get("action_items", []), violations, rca)

        return CorrectiveActionReport(
            car_number=car_number,
            rig_id=data.rig_id,
            overall_severity=overall_severity,
            audit_status=AuditStatus.PENDING if requires_director_signoff else AuditStatus.COMPLETED,
            executive_summary=exec_summary,
            regulatory_citations=citations,
            identified_violations=violations,
            root_cause_analysis=rca,
            referenced_sops=referenced_sops,
            action_items=actions,
            requires_safety_director_signoff=requires_director_signoff,
            osha_reportable=osha_reportable,
        )

    def _compute_overall_severity(self, violations: List[RuleViolation]) -> SeverityLevel:
        if not violations:
            return SeverityLevel.COMPLIANT
        severities = [v.severity for v in violations]
        if SeverityLevel.CRITICAL in severities:
            return SeverityLevel.CRITICAL
        if SeverityLevel.HIGH in severities:
            return SeverityLevel.HIGH
        if SeverityLevel.MEDIUM in severities:
            return SeverityLevel.MEDIUM
        return SeverityLevel.LOW

    def _call_llm_for_capa(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        rca: Optional[RootCauseAnalysisResult],
        sops: List[RetrievedSOP],
        severity: SeverityLevel,
    ) -> dict:
        prompt = f"""Generate CAR action items for incident on Rig {data.rig_id}.
Severity: {severity.value}
Summary: {data.summary}
Violations: {json.dumps([v.model_dump() for v in violations])}
RCA Statement: {rca.root_cause_statement if rca else 'N/A'}
Primary Cause Category: {rca.primary_category.value if rca else 'N/A'}
Relevant SOPs: {', '.join([s.doc_id for s in sops])}

Return JSON with executive_summary and 3-4 structured CAPA action items (Containment, Corrective, Preventive)."""

        try:
            response = self.llm.invoke([
                SystemMessage(content=CAR_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            text = response.content if hasattr(response, "content") else str(response)
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            json_str = match.group(1) if match else text.strip()
            return json.loads(json_str)
        except Exception as e:
            logger.debug("LLM CAR generation fell back to deterministic generator: %s", e)
            return {}

    def _generate_default_summary(
        self,
        data: UnifiedSafetyData,
        violations: List[RuleViolation],
        severity: SeverityLevel,
    ) -> str:
        if severity == SeverityLevel.COMPLIANT:
            return f"Operational audit for Rig {data.rig_id} completed successfully. No non-conformances identified against API RP 54 or company SOPs."

        v_names = ", ".join([v.rule_name for v in violations[:3]])
        return (
            f"Formal Corrective Action Report generated for Rig {data.rig_id}. "
            f"Audit revealed {len(violations)} non-conformance(s) rated as {severity.value}: {v_names}. "
            "Immediate containment required prior to operational resumption."
        )

    def _build_action_items(
        self,
        raw_items: List[dict],
        violations: List[RuleViolation],
        rca: Optional[RootCauseAnalysisResult],
    ) -> List[CAPAItem]:
        items: List[CAPAItem] = []

        if raw_items:
            for idx, item in enumerate(raw_items, start=1):
                items.append(
                    CAPAItem(
                        action_id=item.get("action_id", f"CAPA-{idx:02d}"),
                        action_type=item.get("action_type", "CORRECTIVE"),
                        description=item.get("description", "Execute barrier remediation"),
                        responsible_party=item.get("responsible_party", "Rig Superintendent"),
                        target_completion_days=int(item.get("target_completion_days", 7)),
                        regulatory_mandate=item.get("regulatory_mandate"),
                        verification_method=item.get("verification_method", "Documented verification sign-off"),
                    )
                )
            return items

        # Deterministic default CAPA items based on violations and 5 Whys
        # Item 1: Immediate Containment
        primary_violation = violations[0] if violations else None
        containment_desc = (
            primary_violation.recommended_immediate_action
            if primary_violation
            else "Halt operational sequence in affected sector and verify safe isolation."
        )
        items.append(
            CAPAItem(
                action_id="CAPA-01",
                action_type="CONTAINMENT",
                description=containment_desc,
                responsible_party="Rig Superintendent & HSE Lead",
                target_completion_days=1,
                regulatory_mandate=primary_violation.citation if primary_violation else "API RP 54",
                verification_method="Physical site inspection and zero-energy / zero-pressure sign-off log",
            )
        )

        # Item 2: Corrective Action
        items.append(
            CAPAItem(
                action_id="CAPA-02",
                action_type="CORRECTIVE",
                description=(
                    "Re-certify and pressure test affected sub-system in accordance with SOP-042 / SOP-108. "
                    "Conduct mandatory stand-down and tailgate safety brief for all incoming tour personnel."
                ),
                responsible_party="Toolpusher & Maintenance Foreman",
                target_completion_days=3,
                regulatory_mandate=primary_violation.citation if primary_violation else "API RP 54",
                verification_method="Signed calibrated chart recorder pressure test and JSA attendance roster",
            )
        )

        # Item 3: Preventive Action (Systemic)
        rca_statement = rca.root_cause_statement if rca else "Shift handover and barrier verification governance"
        items.append(
            CAPAItem(
                action_id="CAPA-03",
                action_type="PREVENTIVE",
                description=(
                    f"Remediate systemic root cause: {rca_statement}. Implement digital supervisory barrier "
                    "verification gate in Tour Sheet logging software to prevent operational resumption without QA/QC sign-off."
                ),
                responsible_party="Corporate VP of Drilling Operations & HSE Director",
                target_completion_days=30,
                regulatory_mandate="ISO 45001 / OSHA 1910.119 (PSM)",
                verification_method="Management of Change (MOC) sign-off and enterprise audit verification",
            )
        )

        return items
