import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from safety_graph_orchestrator.core.models import (
    InputType,
    JSAStep,
    ParsedJSA,
    SeverityLevel,
    UnifiedSafetyData,
)
from safety_graph_orchestrator.parsers.base import BaseSafetyParser


class JSAParser(BaseSafetyParser):
    """Parses Job Safety Analysis (JSA / JHA) risk matrices."""

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
        steps: List[JSAStep] = []
        unmitigated_hazards: List[str] = []
        ppe_gap = False
        fall_height = float(data.get("fall_height_ft", 0.0))
        high_pressure_psi = float(data.get("high_pressure_psi", 0.0))

        for idx, item in enumerate(data.get("steps", []), start=1):
            hazards = item.get("potential_hazards", [])
            controls = item.get("required_controls", [])
            ppe = item.get("ppe_required", [])
            risk_str = str(item.get("residual_risk_level", "LOW")).upper()
            risk = SeverityLevel[risk_str] if risk_str in SeverityLevel.__members__ else SeverityLevel.LOW

            # If hazards exist without controls, record unmitigated
            if hazards and not controls:
                unmitigated_hazards.extend([f"Step {idx}: {h} has zero controls assigned" for h in hazards])

            # Check if working at height lacks fall arrest
            for h in hazards:
                h_lower = h.lower()
                if "fall" in h_lower or "height" in h_lower or "derrick" in h_lower:
                    if not fall_height:
                        fall_height = 20.0
                    has_fall_control = any("harness" in c.lower() or "lanyard" in c.lower() or "tie-off" in c.lower() for c in controls + ppe)
                    if not has_fall_control:
                        unmitigated_hazards.append(f"Step {idx}: Fall hazard identified without harness/100% tie-off control")
                        ppe_gap = True

            steps.append(
                JSAStep(
                    step_number=item.get("step_number", idx),
                    task_description=item.get("task_description", ""),
                    potential_hazards=hazards,
                    required_controls=controls,
                    ppe_required=ppe,
                    residual_risk_level=risk,
                )
            )

        parsed_jsa = ParsedJSA(
            jsa_number=data.get("jsa_number", f"JSA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"),
            task_title=data.get("task_title", "Operational Task"),
            rig_id=data.get("rig_id", "RIG-UNKNOWN"),
            date=data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            permit_to_work_required=bool(data.get("permit_to_work_required", False)),
            permit_type=data.get("permit_type"),
            steps=steps,
            crew_members_present=data.get("crew_members_present", []),
            supervisor_approval=bool(data.get("supervisor_approval", True)),
        )

        summary = (
            f"JSA Audit ({parsed_jsa.jsa_number}) for '{parsed_jsa.task_title}' on Rig {parsed_jsa.rig_id}. "
            f"Steps evaluated: {len(parsed_jsa.steps)}. Deficiencies identified: {len(unmitigated_hazards)}."
        )

        return UnifiedSafetyData(
            input_type=InputType.JSA,
            source_id=parsed_jsa.jsa_number,
            rig_id=parsed_jsa.rig_id,
            timestamp=parsed_jsa.date,
            summary=summary,
            raw_text=raw_text,
            h2s_ppm=float(data.get("h2s_ppm", 0.0)),
            lel_pct=float(data.get("lel_pct", 0.0)),
            high_pressure_psi=high_pressure_psi,
            fall_height_ft=fall_height,
            hot_work_active=bool(data.get("hot_work_active", False)) or (parsed_jsa.permit_type or "").upper() == "HOT_WORK",
            swa_invoked=False,
            premature_restart=False,
            lockout_tagout_verified=not ("loto" in raw_text.lower() and "unverified" in raw_text.lower()),
            ppe_compliance_gap=ppe_gap,
            unmitigated_hazards=unmitigated_hazards,
            metadata={"parsed_jsa": parsed_jsa.model_dump()},
        )

    def _parse_unstructured_text(self, text: str) -> UnifiedSafetyData:
        task_match = re.search(r"(?:Task|Job Title|Activity)\s*[:\-]?\s*([A-Za-z0-9\s\-]+?)(?:,|\n|$)", text, re.IGNORECASE)
        task_title = task_match.group(1).strip() if task_match else "Rig Operations Task"

        rig_match = re.search(r"(?:Rig|RIG)\s*[:#-]?\s*([A-Za-z0-9\-]+)", text)
        rig_id = rig_match.group(1) if rig_match else "RIG-UNKNOWN"

        fall_height = 0.0
        if re.search(r"(height|derrick|monkey board|mast)", text, re.IGNORECASE):
            fall_height = 30.0

        unmitigated = []
        ppe_gap = False

        if fall_height >= 6.0:
            if re.search(r"(no harness|without harness|no fall arrest|no tie-off|missing harness|controls:\s*none)", text, re.IGNORECASE):
                unmitigated.append(f"Elevation fall hazard ({fall_height} ft) without verified harness or 100% tie-off")
                ppe_gap = True

        if re.search(r"(pinch point|crush|amputation)", text, re.IGNORECASE) and not re.search(r"(impact gloves|push pole|hands off)", text, re.IGNORECASE):
            unmitigated.append("Pinch point hazard identified without barrier control")
            ppe_gap = True

        summary = f"Unstructured JSA for {task_title} on Rig {rig_id}."

        return UnifiedSafetyData(
            input_type=InputType.JSA,
            source_id=f"JSA-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
            rig_id=rig_id,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            summary=summary,
            raw_text=text,
            h2s_ppm=0.0,
            lel_pct=0.0,
            high_pressure_psi=0.0,
            fall_height_ft=fall_height,
            hot_work_active=bool(re.search(r"(hot work|welding|cutting)", text, re.IGNORECASE)),
            swa_invoked=False,
            premature_restart=False,
            lockout_tagout_verified=True,
            ppe_compliance_gap=ppe_gap,
            unmitigated_hazards=unmitigated,
            metadata={"task_title": task_title},
        )
