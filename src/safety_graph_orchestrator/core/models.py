from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class InputType(str, Enum):
    DDR = "DDR"  # Daily Drilling Report
    SWA = "SWA"  # Stop Work Authority / Incident Notification
    JSA = "JSA"  # Job Safety Analysis
    AUTO = "AUTO"  # Auto-detect from text


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"  # Immediate life safety or catastrophic environmental risk (Tier 1)
    HIGH = "HIGH"          # Significant regulatory breach or serious injury potential (Tier 2)
    MEDIUM = "MEDIUM"      # Moderate procedural non-conformance (Tier 3)
    LOW = "LOW"            # Minor housekeeping or documentation lag (Tier 4)
    COMPLIANT = "COMPLIANT"# No safety violations detected


class RegulatoryStandard(str, Enum):
    OSHA_1910_120 = "OSHA 29 CFR 1910.120 (HAZWOPER / Toxic Gas Contingency)"
    OSHA_1910_147 = "OSHA 29 CFR 1910.147 (Lockout/Tagout - Hazardous Energy)"
    OSHA_1910_119 = "OSHA 29 CFR 1910.119 (Process Safety Management)"
    OSHA_1910_132 = "OSHA 29 CFR 1910.132 (Personal Protective Equipment)"
    OSHA_1926_501 = "OSHA 29 CFR 1926.501 (Fall Protection in Construction/Derrick)"
    API_RP_54 = "API RP 54 (Occupational Safety for Oil & Gas Well Operations)"
    API_SPEC_16D = "API Spec 16D (Control Systems for Drilling Well Control Equipment)"
    IADC_SMS = "IADC Safety Management System Guidelines"
    COMPANY_SOP = "Internal Company Standard Operating Procedure"


class RootCauseCategory(str, Enum):
    HUMAN_FACTORS = "Human Factors (Situational Awareness / Fatigue)"
    EQUIPMENT_INTEGRITY = "Equipment Integrity & Mechanical Failure"
    PROCEDURAL_COMPLIANCE = "Procedural Adherence & SOP Gap"
    MANAGEMENT_SYSTEMS = "Management Systems & Resource Allocation"
    COMMUNICATION_HANDOVER = "Communication & Shift Handover Gap"
    HAZARD_IDENTIFICATION = "Inadequate Pre-job Hazard Identification"


class AuditStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ESCALATED_TO_HUMAN = "ESCALATED_TO_HUMAN"
    REJECTED = "REJECTED"


# -------------------------------------------------------------------------
# Ingestion & Parsed Operational Schemas
# -------------------------------------------------------------------------

class OperationalInterval(BaseModel):
    start_time: str = Field(description="Interval start time, e.g. 06:00")
    end_time: str = Field(description="Interval end time, e.g. 08:30")
    duration_hours: float = Field(default=0.0)
    operation_code: Optional[str] = Field(default=None, description="e.g. DRILL, TRIP, CSG, RIGREP")
    activity_description: str = Field(description="Detailed operational notes")
    safety_observations: List[str] = Field(default_factory=list)


class ParsedDDR(BaseModel):
    well_name: str
    rig_id: str
    report_date: str
    current_depth_ft: float = 0.0
    mud_weight_ppg: float = 0.0
    flow_line_temp_f: Optional[float] = None
    h2s_detected_ppm: float = 0.0
    lel_combustible_pct: float = 0.0
    intervals: List[OperationalInterval] = Field(default_factory=list)
    active_permits: List[str] = Field(default_factory=list)
    bha_description: Optional[str] = None
    safety_remarks: List[str] = Field(default_factory=list)
    incidents_reported: List[str] = Field(default_factory=list)


class ParsedSWA(BaseModel):
    incident_id: str
    rig_id: str
    datetime_called: str
    caller_role: str = Field(description="e.g. Floorhand, Derrickman, HSE Specialist")
    rig_location: str = Field(description="e.g. Choke Manifold, Monkey Board, Mud Pit 2")
    hazard_description: str
    immediate_actions_taken: List[str] = Field(default_factory=list)
    potential_severity: SeverityLevel = SeverityLevel.HIGH
    operations_halted: bool = True
    operations_resumed_prematurely: bool = False
    supervisor_signoff: bool = False


class JSAStep(BaseModel):
    step_number: int
    task_description: str
    potential_hazards: List[str] = Field(default_factory=list)
    required_controls: List[str] = Field(default_factory=list)
    ppe_required: List[str] = Field(default_factory=list)
    residual_risk_level: SeverityLevel = SeverityLevel.LOW


class ParsedJSA(BaseModel):
    jsa_number: str
    task_title: str
    rig_id: str
    date: str
    permit_to_work_required: bool = False
    permit_type: Optional[str] = None
    steps: List[JSAStep] = Field(default_factory=list)
    crew_members_present: List[str] = Field(default_factory=list)
    supervisor_approval: bool = True


class UnifiedSafetyData(BaseModel):
    """Unified normalized domain representation feeding into the rule engine and RCA."""
    input_type: InputType
    source_id: str
    rig_id: str
    timestamp: str
    summary: str
    raw_text: str
    mud_weight_ppg: float = 0.0
    h2s_ppm: float = 0.0
    lel_pct: float = 0.0
    high_pressure_psi: float = 0.0
    fall_height_ft: float = 0.0
    hot_work_active: bool = False
    swa_invoked: bool = False
    premature_restart: bool = False
    lockout_tagout_verified: bool = True
    ppe_compliance_gap: bool = False
    unmitigated_hazards: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# -------------------------------------------------------------------------
# Rules, RAG, RCA, and CAR Schemas
# -------------------------------------------------------------------------

class RuleViolation(BaseModel):
    rule_id: str
    rule_name: str
    severity: SeverityLevel
    regulatory_standard: RegulatoryStandard
    citation: str
    description: str
    evidence: str
    recommended_immediate_action: str


class RetrievedSOP(BaseModel):
    doc_id: str
    title: str
    standard_reference: str
    content: str
    relevance_score: float
    category: str


class AgentPerspective(BaseModel):
    """Structured perspective submitted by a specialized domain agent during deliberation."""
    agent_role: str = Field(description="e.g. Drilling Operations, OSHA Compliance, Equipment Reliability")
    key_findings: List[str] = Field(default_factory=list)
    causal_assessment: str = Field(description="Primary contributing factor from this agent's specialty")
    identified_vulnerabilities: List[str] = Field(default_factory=list)
    recommended_focus: str = Field(description="Key focus area for CAPA containment")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class FiveWhysStep(BaseModel):
    level: int = Field(ge=1, le=5)
    question: str
    answer: str
    causal_category: RootCauseCategory
    confidence_score: float = Field(ge=0.0, le=1.0)


class RootCauseAnalysisResult(BaseModel):
    incident_summary: str
    direct_cause: str
    contributing_factors: List[str] = Field(default_factory=list)
    deliberation_perspectives: List[AgentPerspective] = Field(default_factory=list)
    five_whys: List[FiveWhysStep] = Field(default_factory=list)
    root_cause_statement: str
    primary_category: RootCauseCategory
    systemic_failure_pattern: str


class CAPAItem(BaseModel):
    action_id: str
    action_type: str = Field(description="CONTAINMENT, CORRECTIVE, or PREVENTIVE")
    description: str
    responsible_party: str
    target_completion_days: int
    regulatory_mandate: Optional[str] = None
    verification_method: str


class CorrectiveActionReport(BaseModel):
    car_number: str
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rig_id: str
    overall_severity: SeverityLevel
    audit_status: AuditStatus
    executive_summary: str
    regulatory_citations: List[str] = Field(default_factory=list)
    identified_violations: List[RuleViolation] = Field(default_factory=list)
    root_cause_analysis: Optional[RootCauseAnalysisResult] = None
    referenced_sops: List[str] = Field(default_factory=list)
    action_items: List[CAPAItem] = Field(default_factory=list)
    requires_safety_director_signoff: bool = False
    osha_reportable: bool = False


class AuditLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    node_name: str
    action: str
    details: Dict[str, Any] = Field(default_factory=dict)
