import json
import re
from datetime import datetime, timezone
from typing import Any, Dict

from safety_graph_orchestrator.core.models import (
    InputType,
    ParsedSWA,
    SeverityLevel,
    UnifiedSafetyData,
)
from safety_graph_orchestrator.parsers.base import BaseSafetyParser


class SWAParser(BaseSafetyParser):
    """Parses Stop Work Authority (SWA) notifications and incident logs."""

    def parse(self, raw_text: str) -> UnifiedSafetyData:
        raw_stripped = raw_text.strip()
        if raw_stripped.startswith("{") and raw_stripped.endswith("}"):
            try:
                data = json.loads(raw_stripped)
                return self._parse_json_dict(data, raw_text)
            except json.JSONDecodeError:
                pass

        return self._parse_unstructured_text(raw_text)

    def _parse_json_dict(self, data: Dict[str, Any], raw_text: str) -> UnifiedSafetyData:
        severity_str = str(data.get("potential_severity", "HIGH")).upper()
        severity = SeverityLevel[severity_str] if severity_str in SeverityLevel.__members__ else SeverityLevel.HIGH

        parsed_swa = ParsedSWA(
            incident_id=data.get("incident_id", f"SWA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"),
            rig_id=data.get("rig_id", "RIG-UNKNOWN"),
            datetime_called=data.get("datetime_called", datetime.now(timezone.utc).isoformat()),
            caller_role=data.get("caller_role", "Drilling Crew Member"),
            rig_location=data.get("rig_location", "Rig Floor"),
            hazard_description=data.get("hazard_description", ""),
            immediate_actions_taken=data.get("immediate_actions_taken", []),
            potential_severity=severity,
            operations_halted=bool(data.get("operations_halted", True)),
            operations_resumed_prematurely=bool(data.get("operations_resumed_prematurely", False)),
            supervisor_signoff=bool(data.get("supervisor_signoff", False)),
        )

        h2s_ppm = float(data.get("h2s_ppm", 0.0))
        high_pressure_psi = float(data.get("high_pressure_psi", 0.0))
        fall_height_ft = float(data.get("fall_height_ft", 0.0))

        # Check description for keywords if metrics omitted
        desc_lower = parsed_swa.hazard_description.lower()
        if not h2s_ppm:
            match = re.search(r"(\d+(?:\.\d+)?)\s*ppm", desc_lower)
            if match:
                h2s_ppm = float(match.group(1))

        if not high_pressure_psi:
            match = re.search(r"(\d{3,5})\s*psi", desc_lower)
            if match:
                high_pressure_psi = float(match.group(1))

        if not fall_height_ft and ("monkey board" in desc_lower or "derrick" in desc_lower or "height" in desc_lower):
            fall_height_ft = 85.0  # Standard monkey board height

        summary = (
            f"SWA Invoked ({parsed_swa.incident_id}) on Rig {parsed_swa.rig_id} at {parsed_swa.rig_location} "
            f"by {parsed_swa.caller_role}. Hazard: {parsed_swa.hazard_description}. "
            f"Premature restart: {parsed_swa.operations_resumed_prematurely}."
        )

        return UnifiedSafetyData(
            input_type=InputType.SWA,
            source_id=parsed_swa.incident_id,
            rig_id=parsed_swa.rig_id,
            timestamp=parsed_swa.datetime_called,
            summary=summary,
            raw_text=raw_text,
            h2s_ppm=h2s_ppm,
            lel_pct=float(data.get("lel_pct", 0.0)),
            high_pressure_psi=high_pressure_psi,
            fall_height_ft=fall_height_ft,
            hot_work_active=bool(data.get("hot_work_active", False)) or "hot work" in desc_lower or "welding" in desc_lower,
            swa_invoked=True,
            premature_restart=parsed_swa.operations_resumed_prematurely,
            lockout_tagout_verified=bool(data.get("lockout_tagout_verified", True)),
            ppe_compliance_gap=bool(data.get("ppe_compliance_gap", False)),
            unmitigated_hazards=[parsed_swa.hazard_description],
            metadata={"parsed_swa": parsed_swa.model_dump()},
        )

    def _parse_unstructured_text(self, text: str) -> UnifiedSafetyData:
        # Regex extraction
        caller_match = re.search(r"(?:Caller|Reported By|Initiated by)\s*[:\-]?\s*([A-Za-z0-9\s]+?)(?:,|\n|$)", text, re.IGNORECASE)
        caller_role = caller_match.group(1).strip() if caller_match else "Rig Crew Member"

        rig_match = re.search(r"(?:Rig|RIG)\s*[:#-]?\s*([A-Za-z0-9\-]+)", text)
        rig_id = rig_match.group(1) if rig_match else "RIG-UNKNOWN"

        location_match = re.search(r"(?:Location|Area|Section)\s*[:\-]?\s*([A-Za-z0-9\s\-]+?)(?:,|\n|$)", text, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else "Rig Floor / Choke Manifold"

        psi_match = re.search(r"(\d{3,5})\s*psi", text, re.IGNORECASE)
        psi = float(psi_match.group(1)) if psi_match else 0.0

        h2s_match = re.search(r"(\d+(?:\.\d+)?)\s*ppm", text, re.IGNORECASE)
        h2s_ppm = float(h2s_match.group(1)) if h2s_match else 0.0

        premature_restart = bool(
            re.search(r"(resumed without|resumed before|bypassed sign-off|restarted without|restarted before|bypassed lock)", text, re.IGNORECASE)
        )

        incident_id = f"SWA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        summary = f"Stop Work Authority invoked on Rig {rig_id} ({location}) by {caller_role}."

        return UnifiedSafetyData(
            input_type=InputType.SWA,
            source_id=incident_id,
            rig_id=rig_id,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            summary=summary,
            raw_text=text,
            h2s_ppm=h2s_ppm,
            lel_pct=0.0,
            high_pressure_psi=psi,
            fall_height_ft=0.0,
            hot_work_active=bool(re.search(r"(welding|cutting|hot work)", text, re.IGNORECASE)),
            swa_invoked=True,
            premature_restart=premature_restart,
            lockout_tagout_verified=True,
            ppe_compliance_gap=False,
            unmitigated_hazards=[text[:300]],
            metadata={"caller_role": caller_role, "location": location},
        )
