import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from safety_graph_orchestrator.core.models import InputType, UnifiedSafetyData

logger = logging.getLogger(__name__)


class WITSMLRecord(BaseModel):
    well_name: str
    rig_id: str
    timestamp: str
    depth_ft: float = 0.0
    mud_weight_ppg: float = 0.0
    standpipe_pressure_psi: float = 0.0
    h2s_ppm: float = 0.0
    lel_pct: float = 0.0
    operations_summary: str = ""
    hazards_identified: List[str] = Field(default_factory=list)


class WITSMLParser:
    """Parses standard WITSML 1.4 / 2.0 XML logs and operational risk objects."""

    def parse(self, xml_content: str) -> UnifiedSafetyData:
        try:
            # Strip XML namespace prefixes (e.g. <witsml:mudLog> -> <mudLog>)
            clean_xml = re.sub(r'<(/)?([a-zA-Z0-9_\-]+):', r'<\1', xml_content)
            clean_xml = re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', clean_xml)
            root = ET.fromstring(clean_xml)
        except Exception as e:
            logger.error("WITSML XML parse error: %s", e)
            raise ValueError(f"Malformed WITSML XML payload: {e}")

        # Extract well and rig names
        well_name = root.findtext(".//nameWell") or root.findtext(".//wellName") or "WITSML-WELL"
        rig_id = root.findtext(".//nameRig") or root.findtext(".//rigName") or "RIG-OFFSHORE-01"
        timestamp = root.findtext(".//dTim") or root.findtext(".//creationDate") or datetime.now(timezone.utc).isoformat()

        # Extract operational metrics
        depth_ft = float(root.findtext(".//md") or root.findtext(".//holeDepth") or 0.0)
        mud_weight = float(root.findtext(".//density") or root.findtext(".//mudWeight") or 10.0)
        pressure_psi = float(root.findtext(".//pressure") or root.findtext(".//standpipePressure") or 0.0)
        h2s_ppm = float(root.findtext(".//h2s") or root.findtext(".//gasH2S") or 0.0)
        lel_pct = float(root.findtext(".//lel") or root.findtext(".//gasCombustible") or 0.0)

        # Risk / incident remarks
        remarks = []
        for elem in root.findall(".//description") + root.findall(".//comment") + root.findall(".//riskSummary"):
            if elem.text and elem.text.strip():
                remarks.append(elem.text.strip())

        raw_summary = " ".join(remarks) or "WITSML Operational Telemetry Record"
        swa_invoked = "stop work" in raw_summary.lower() or "swa" in raw_summary.lower() or h2s_ppm >= 10.0 or pressure_psi >= 4500.0
        premature_restart = "resumed without" in raw_summary.lower() or "restarted" in raw_summary.lower()

        unmitigated_hazards = []
        if h2s_ppm >= 10.0:
            unmitigated_hazards.append(f"WITSML Log: Toxic H2S gas detected at {h2s_ppm} ppm")
        if pressure_psi >= 3500.0:
            unmitigated_hazards.append(f"WITSML Log: High pressure wellbore condition at {pressure_psi} PSI")
        if remarks:
            unmitigated_hazards.extend(remarks[:3])

        summary = (
            f"WITSML Real-Time Log for Well {well_name} on {rig_id}. "
            f"Depth: {depth_ft} ft | Mud: {mud_weight} ppg | Pressure: {pressure_psi} PSI | H2S: {h2s_ppm} ppm."
        )

        return UnifiedSafetyData(
            input_type=InputType.DDR,
            source_id=f"WITSML_{rig_id}_{int(depth_ft)}",
            rig_id=rig_id,
            timestamp=timestamp,
            summary=summary,
            raw_text=xml_content,
            mud_weight_ppg=mud_weight,
            h2s_ppm=h2s_ppm,
            lel_pct=lel_pct,
            high_pressure_psi=pressure_psi,
            fall_height_ft=0.0,
            hot_work_active="hot work" in raw_summary.lower() or "welding" in raw_summary.lower(),
            swa_invoked=swa_invoked,
            premature_restart=premature_restart,
            lockout_tagout_verified=True,
            ppe_compliance_gap=False,
            unmitigated_hazards=unmitigated_hazards,
            metadata={"well_name": well_name, "depth_ft": depth_ft, "witsml_remarks": remarks},
        )
