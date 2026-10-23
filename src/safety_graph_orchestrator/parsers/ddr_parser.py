import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from safety_graph_orchestrator.core.models import (
    InputType,
    OperationalInterval,
    ParsedDDR,
    UnifiedSafetyData,
)
from safety_graph_orchestrator.parsers.base import BaseSafetyParser


class DDRParser(BaseSafetyParser):
    """Parses Daily Drilling Reports (DDR) from JSON payloads or unstructured tour sheets."""

    def parse(self, raw_text: str) -> UnifiedSafetyData:
        # Check if raw_text is valid JSON
        raw_text_stripped = raw_text.strip()
        if raw_text_stripped.startswith("{") and raw_text_stripped.endswith("}"):
            try:
                data = json.loads(raw_text_stripped)
                return self._parse_json_dict(data, raw_text)
            except json.JSONDecodeError:
                pass

        return self._parse_unstructured_text(raw_text)

    def _parse_json_dict(self, data: Dict[str, Any], raw_text: str) -> UnifiedSafetyData:
        intervals: List[OperationalInterval] = []
        for item in data.get("intervals", []):
            intervals.append(
                OperationalInterval(
                    start_time=item.get("start_time", "00:00"),
                    end_time=item.get("end_time", "00:00"),
                    duration_hours=float(item.get("duration_hours", 0.0)),
                    operation_code=item.get("operation_code"),
                    activity_description=item.get("activity_description", ""),
                    safety_observations=item.get("safety_observations", []),
                )
            )

        parsed_ddr = ParsedDDR(
            well_name=data.get("well_name", "UNKNOWN-WELL"),
            rig_id=data.get("rig_id", "RIG-UNKNOWN"),
            report_date=data.get("report_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            current_depth_ft=float(data.get("current_depth_ft", 0.0)),
            mud_weight_ppg=float(data.get("mud_weight_ppg", 0.0)),
            flow_line_temp_f=float(data["flow_line_temp_f"]) if data.get("flow_line_temp_f") is not None else None,
            h2s_detected_ppm=float(data.get("h2s_detected_ppm", 0.0)),
            lel_combustible_pct=float(data.get("lel_combustible_pct", 0.0)),
            intervals=intervals,
            active_permits=data.get("active_permits", []),
            bha_description=data.get("bha_description"),
            safety_remarks=data.get("safety_remarks", []),
            incidents_reported=data.get("incidents_reported", []),
        )

        # Extract flags for unified representation
        high_pressure_psi = float(data.get("high_pressure_psi", 0.0))
        if not high_pressure_psi:
            # Check text for pressure indicators
            psi_match = re.search(r"(\d{3,5})\s*psi", raw_text, re.IGNORECASE)
            if psi_match:
                high_pressure_psi = float(psi_match.group(1))

        swa_invoked = bool(data.get("swa_invoked", False)) or bool(parsed_ddr.incidents_reported)
        premature_restart = bool(data.get("premature_restart", False))
        hot_work = "HOT_WORK" in [p.upper() for p in parsed_ddr.active_permits] or "welding" in raw_text.lower()
        ppe_gap = bool(data.get("ppe_compliance_gap", False))

        summary = (
            f"DDR for Well {parsed_ddr.well_name} on Rig {parsed_ddr.rig_id} "
            f"(Depth: {parsed_ddr.current_depth_ft} ft, Mud: {parsed_ddr.mud_weight_ppg} ppg, "
            f"H2S: {parsed_ddr.h2s_detected_ppm} ppm). "
            f"Reported Incidents: {len(parsed_ddr.incidents_reported)}."
        )

        return UnifiedSafetyData(
            input_type=InputType.DDR,
            source_id=f"{parsed_ddr.rig_id}_{parsed_ddr.report_date}",
            rig_id=parsed_ddr.rig_id,
            timestamp=parsed_ddr.report_date,
            summary=summary,
            raw_text=raw_text,
            mud_weight_ppg=parsed_ddr.mud_weight_ppg,
            h2s_ppm=parsed_ddr.h2s_detected_ppm,
            lel_pct=parsed_ddr.lel_combustible_pct,
            high_pressure_psi=high_pressure_psi,
            fall_height_ft=float(data.get("fall_height_ft", 0.0)),
            hot_work_active=hot_work,
            swa_invoked=swa_invoked,
            premature_restart=premature_restart,
            lockout_tagout_verified=data.get("lockout_tagout_verified", True),
            ppe_compliance_gap=ppe_gap,
            unmitigated_hazards=parsed_ddr.incidents_reported + parsed_ddr.safety_remarks,
            metadata={"parsed_ddr": parsed_ddr.model_dump()},
        )

    def _parse_unstructured_text(self, text: str) -> UnifiedSafetyData:
        # Extract Rig ID
        rig_match = re.search(r"(?:Rig|RIG)\s*[:#-]?\s*([A-Za-z0-9\-]+)", text)
        rig_id = rig_match.group(1) if rig_match else "RIG-ALPHA"

        # Extract Well Name
        well_match = re.search(r"(?:Well|WELL)\s*[:#-]?\s*([A-Za-z0-9\-_]+)", text)
        well_name = well_match.group(1) if well_match else "WELL-01"

        # Extract Mud Weight
        mud_match = re.search(r"(\d{1,2}(?:\.\d+)?)\s*(?:ppg|PPG)", text)
        mud_weight = float(mud_match.group(1)) if mud_match else 9.2

        # Extract H2S (both 'H2S: 15 ppm' and '15 ppm H2S')
        h2s_match = re.search(r"(?:(?:H2S|h2s)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*ppm|(\d+(?:\.\d+)?)\s*ppm\s*(?:H2S|h2s))", text, re.IGNORECASE)
        if h2s_match:
            h2s_ppm = float(h2s_match.group(1) or h2s_match.group(2))
        else:
            h2s_ppm = 0.0

        # Extract Combustible LEL
        lel_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*LEL", text, re.IGNORECASE)
        lel_pct = float(lel_match.group(1)) if lel_match else 0.0

        # Extract Pressure
        psi_match = re.search(r"(\d{3,5})\s*psi", text, re.IGNORECASE)
        psi = float(psi_match.group(1)) if psi_match else 0.0

        # Detect SWA or incidents
        swa_invoked = bool(re.search(r"(stop work|swa invoked|shut down|halted)", text, re.IGNORECASE))
        premature_restart = bool(re.search(r"(resumed without|restarted before|bypassed sign-off|no supervisor approval)", text, re.IGNORECASE))
        hot_work = bool(re.search(r"(welding|cutting torch|grinding|hot work)", text, re.IGNORECASE))
        ppe_gap = bool(re.search(r"(no harness|without frc|missing face shield|no safety glasses)", text, re.IGNORECASE))

        # Extract interval operations if formatted like "06:00 - 12:00: Tripping in hole"
        intervals = []
        interval_matches = re.findall(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\s*[:\-]?\s*([^\n]+)", text)
        for start, end, desc in interval_matches:
            intervals.append(
                OperationalInterval(
                    start_time=start,
                    end_time=end,
                    activity_description=desc.strip(),
                )
            )

        incidents = []
        if swa_invoked:
            incidents.append("Stop Work Authority recorded in daily drilling log")
        if h2s_ppm > 10.0:
            incidents.append(f"Elevated H2S gas detection ({h2s_ppm} ppm)")
        if psi > 3000.0:
            incidents.append(f"High pressure operations active ({psi} PSI)")

        summary = f"DDR parsed from unstructured tour log for Rig {rig_id}, Well {well_name}. Mud weight: {mud_weight} ppg, H2S: {h2s_ppm} ppm."

        return UnifiedSafetyData(
            input_type=InputType.DDR,
            source_id=f"{rig_id}_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            rig_id=rig_id,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            summary=summary,
            raw_text=text,
            mud_weight_ppg=mud_weight,
            h2s_ppm=h2s_ppm,
            lel_pct=lel_pct,
            high_pressure_psi=psi,
            fall_height_ft=0.0,
            hot_work_active=hot_work,
            swa_invoked=swa_invoked,
            premature_restart=premature_restart,
            lockout_tagout_verified=True,
            ppe_compliance_gap=ppe_gap,
            unmitigated_hazards=incidents,
            metadata={"extracted_intervals_count": len(intervals)},
        )
