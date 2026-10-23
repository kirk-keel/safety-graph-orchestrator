from collections import deque
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Deque, Dict, List, Optional
from pydantic import BaseModel, Field

from safety_graph_orchestrator.core.models import InputType, UnifiedSafetyData
from safety_graph_orchestrator.graph.builder import run_safety_audit

logger = logging.getLogger(__name__)


class RigSensorFrame(BaseModel):
    """Single discrete telemetry frame from rig acquisition system."""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rig_id: str
    depth_ft: float
    standpipe_pressure_psi: float
    pit_volume_bbl: float
    flow_in_gpm: float
    flow_out_pct: float
    h2s_ppm: float = 0.0
    lel_pct: float = 0.0
    hookload_klbs: float = 0.0
    activity_code: str = "DRILL"


class EarlyWarningAnomaly(BaseModel):
    anomaly_type: str
    severity: str
    description: str
    detected_at: str
    sensor_frame: RigSensorFrame


class RealTimeEarlyWarningMonitor:
    """Continuously evaluates streaming rig telemetry for well control & gas breach signatures."""

    def __init__(
        self,
        rig_id: str,
        buffer_size: int = 30,
        pit_gain_threshold_bbl: float = 3.0,
        pressure_spike_threshold_psi: float = 400.0,
        h2s_limit_ppm: float = 10.0,
    ):
        self.rig_id = rig_id
        self.buffer_size = buffer_size
        self.pit_gain_threshold = pit_gain_threshold_bbl
        self.pressure_spike_threshold = pressure_spike_threshold_psi
        self.h2s_limit = h2s_limit_ppm

        self.history: Deque[RigSensorFrame] = deque(maxlen=buffer_size)
        self.baseline_pit_volume: Optional[float] = None

    def process_frame(self, frame: RigSensorFrame) -> Optional[EarlyWarningAnomaly]:
        """Process incoming sensor frame and return Anomaly if critical threshold breached."""
        if self.baseline_pit_volume is None:
            self.baseline_pit_volume = frame.pit_volume_bbl

        anomaly = None

        # 1. Check Toxic Gas ($H_2S \ge 10 ppm$)
        if frame.h2s_ppm >= self.h2s_limit:
            anomaly = EarlyWarningAnomaly(
                anomaly_type="TOXIC_GAS_THRESHOLD",
                severity="CRITICAL",
                description=f"Continuous H2S detection at {frame.h2s_ppm} ppm exceeded legal 10.0 ppm PEL.",
                detected_at=frame.timestamp,
                sensor_frame=frame,
            )

        # 2. Check Well Influx / Kick (Pit Volume Gain)
        pit_gain = frame.pit_volume_bbl - self.baseline_pit_volume
        if pit_gain >= self.pit_gain_threshold:
            anomaly = EarlyWarningAnomaly(
                anomaly_type="WELL_INFLUX_KICK",
                severity="CRITICAL",
                description=f"Active pit volume gain (+{pit_gain:.1f} bbls) exceeds 3.0 bbl influx threshold. Flow out indicates formation fluid ingress.",
                detected_at=frame.timestamp,
                sensor_frame=frame,
            )

        # 3. Check High Pressure Spike on Manifold
        if self.history:
            prev_frame = self.history[-1]
            pressure_delta = abs(frame.standpipe_pressure_psi - prev_frame.standpipe_pressure_psi)
            if pressure_delta >= self.pressure_spike_threshold and frame.standpipe_pressure_psi >= 3500.0:
                anomaly = EarlyWarningAnomaly(
                    anomaly_type="MANIFOLD_PRESSURE_SPIKE",
                    severity="HIGH",
                    description=f"Rapid pressure pulsation delta ({pressure_delta:.0f} PSI) under high pressure ({frame.standpipe_pressure_psi} PSI).",
                    detected_at=frame.timestamp,
                    sensor_frame=frame,
                )

        self.history.append(frame)
        return anomaly

    def to_unified_safety_data(self, anomaly: EarlyWarningAnomaly) -> UnifiedSafetyData:
        """Converts real-time sensor anomaly into unified domain data for LangGraph execution."""
        frame = anomaly.sensor_frame
        summary = (
            f"REAL-TIME SENSOR ANOMALY [{anomaly.anomaly_type}] on Rig {frame.rig_id} at Depth {frame.depth_ft} ft. "
            f"{anomaly.description} (Pressure: {frame.standpipe_pressure_psi} PSI, H2S: {frame.h2s_ppm} ppm)."
        )

        return UnifiedSafetyData(
            input_type=InputType.SWA,
            source_id=f"TELEMETRY_{frame.rig_id}_{int(frame.depth_ft)}",
            rig_id=frame.rig_id,
            timestamp=anomaly.detected_at,
            summary=summary,
            raw_text=f"Real-time rig telemetry stream triggered emergency Stop Work Authority. Anomaly: {anomaly.description}",
            mud_weight_ppg=12.5,
            h2s_ppm=frame.h2s_ppm,
            lel_pct=frame.lel_pct,
            high_pressure_psi=frame.standpipe_pressure_psi,
            fall_height_ft=0.0,
            hot_work_active=False,
            swa_invoked=True,
            premature_restart=False,
            lockout_tagout_verified=True,
            ppe_compliance_gap=False,
            unmitigated_hazards=[anomaly.description],
            metadata={"telemetry_anomaly": anomaly.model_dump()},
        )


def simulate_rig_telemetry_stream(
    rig_id: str = "TRANSOCEAN-ORION",
    steps: int = 10,
    inject_kick: bool = True,
) -> List[RigSensorFrame]:
    """Generates synthetic rig telemetry sequence progressing from baseline drilling to a gas influx kick."""
    frames = []
    base_depth = 18400.0
    base_pressure = 3200.0
    base_pit = 450.0

    for i in range(steps):
        # Normal drilling progression
        depth = base_depth + (i * 2.5)
        pressure = base_pressure + (i * 10.0)
        pit = base_pit
        h2s = 0.0
        lel = 0.0
        flow_out = 100.0

        # Inject well kick at step 7 onwards
        if inject_kick and i >= 7:
            pit = base_pit + ((i - 6) * 2.5)  # Pit gain (+2.5 bbls, +5.0 bbls, +7.5 bbls)
            flow_out = 100.0 + ((i - 6) * 15.0)  # Flow out > flow in
            pressure = base_pressure + ((i - 6) * 450.0)  # Pressure kick
            h2s = 14.5  # Sour gas influx
            lel = 8.0

        frames.append(
            RigSensorFrame(
                timestamp=datetime.now(timezone.utc).isoformat(),
                rig_id=rig_id,
                depth_ft=depth,
                standpipe_pressure_psi=pressure,
                pit_volume_bbl=pit,
                flow_in_gpm=650.0,
                flow_out_pct=flow_out,
                h2s_ppm=h2s,
                lel_pct=lel,
                hookload_klbs=240.0,
                activity_code="DRILL",
            )
        )

    return frames
