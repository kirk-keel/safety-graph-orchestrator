from typing import Optional

from safety_graph_orchestrator.core.models import (
    RegulatoryStandard,
    RuleViolation,
    SeverityLevel,
    UnifiedSafetyData,
)
from safety_graph_orchestrator.rules.base import BaseSafetyRule


class H2SToxicGasRule(BaseSafetyRule):
    """Enforces toxic gas monitoring and barrier isolation when H2S >= 10 ppm."""

    rule_id = "RULE-H2S-001"
    rule_name = "H2S Toxic Gas Threshold Exceeded"
    severity = SeverityLevel.CRITICAL
    regulatory_standard = RegulatoryStandard.OSHA_1910_120
    citation = "29 CFR 1910.120 / API RP 54 Section 20.3 (Hydrogen Sulfide Contingency)"

    def evaluate(self, data: UnifiedSafetyData) -> Optional[RuleViolation]:
        if data.h2s_ppm >= 10.0:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                regulatory_standard=self.regulatory_standard,
                citation=self.citation,
                description=(
                    f"Measured H2S concentration reached {data.h2s_ppm} ppm, surpassing the 10 ppm permissible "
                    "exposure limit / continuous action threshold without documented positive pressure SCBA and area evacuation."
                ),
                evidence=f"Reported H2S Level: {data.h2s_ppm} ppm (Threshold: 10.0 ppm). Source: {data.source_id}",
                recommended_immediate_action=(
                    "Immediately halt operations, don 30-minute self-contained breathing apparatus (SCBA), "
                    "muster crew upwind, and activate rig audible/visual toxic gas alarms."
                ),
            )
        return None


class WellControlBarrierRule(BaseSafetyRule):
    """Enforces dual-barrier verification during high-pressure (>3,000 PSI) operations."""

    rule_id = "RULE-WELLCTRL-002"
    rule_name = "High-Pressure Well Control Barrier Degradation"
    severity = SeverityLevel.CRITICAL
    regulatory_standard = RegulatoryStandard.API_SPEC_16D
    citation = "API RP 54 Section 6 & API Spec 16D (Well Control & Choke Manifold Integrity)"

    def evaluate(self, data: UnifiedSafetyData) -> Optional[RuleViolation]:
        is_hp = data.high_pressure_psi >= 3000.0
        has_barrier_leak = any(
            term in data.raw_text.lower()
            for term in ["weeping", "flange leak", "choke leak", "washout", "unseated", "seal breach"]
        )

        if is_hp and has_barrier_leak:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                regulatory_standard=self.regulatory_standard,
                citation=self.citation,
                description=(
                    f"Operating at {data.high_pressure_psi} PSI with an active or suspected pressure-containing "
                    "barrier breach on surface well control equipment (choke manifold or BOP line)."
                ),
                evidence=f"Operating Pressure: {data.high_pressure_psi} PSI. Text indicators: {data.unmitigated_hazards}",
                recommended_immediate_action=(
                    "Isolate active high-pressure line via upstream hydraulic gate valve, bleed off line pressure to zero, "
                    "lock out the line, and replace defective gasket/seal prior to resuming operations."
                ),
            )
        return None


class WorkingAtHeightsRule(BaseSafetyRule):
    """Enforces 100% tie-off fall protection above 6 feet."""

    rule_id = "RULE-FALLPROT-003"
    rule_name = "Working at Heights Fall Protection Deficiency"
    severity = SeverityLevel.HIGH
    regulatory_standard = RegulatoryStandard.OSHA_1926_501
    citation = "29 CFR 1926.501 / API RP 54 Section 9.3 (Personal Fall Arrest Systems)"

    def evaluate(self, data: UnifiedSafetyData) -> Optional[RuleViolation]:
        if data.fall_height_ft >= 6.0 and (data.ppe_compliance_gap or any("fall" in h.lower() for h in data.unmitigated_hazards)):
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                regulatory_standard=self.regulatory_standard,
                citation=self.citation,
                description=(
                    f"Personnel exposed to elevation fall hazard of {data.fall_height_ft} ft without verified "
                    "100% dual lanyard tie-off, certified anchor point, or full body harness inspection."
                ),
                evidence=f"Fall Height: {data.fall_height_ft} ft. Identified Hazards: {data.unmitigated_hazards}",
                recommended_immediate_action=(
                    "Stand down personnel from elevated position (monkey board/mast). Inspect harnesses, inertia reels, "
                    "and secure secondary safety line before allowing work at height to resume."
                ),
            )
        return None


class HotWorkFlammableAtmosphereRule(BaseSafetyRule):
    """Enforces atmospheric testing and hot work permitting near hydrocarbon sources."""

    rule_id = "RULE-HOTWORK-004"
    rule_name = "Hot Work in Combustible Atmosphere"
    severity = SeverityLevel.CRITICAL
    regulatory_standard = RegulatoryStandard.OSHA_1910_119
    citation = "29 CFR 1910.252 / API RP 54 Section 20.1 (Hot Work in Classified Locations)"

    def evaluate(self, data: UnifiedSafetyData) -> Optional[RuleViolation]:
        if data.hot_work_active and (data.lel_pct > 0.0 or any("combustible" in h.lower() or "gas" in h.lower() for h in data.unmitigated_hazards)):
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                regulatory_standard=self.regulatory_standard,
                citation=self.citation,
                description=(
                    f"Hot work (welding/cutting/grinding) active in an unclassified or flammable zone with "
                    f"combustible gas reading ({data.lel_pct}% LEL). Zero tolerance for hot work above 0% LEL."
                ),
                evidence=f"Hot Work Active: {data.hot_work_active}, LEL reading: {data.lel_pct}%",
                recommended_immediate_action=(
                    "Extinguish hot work immediately, shut off welding power units, de-pressurize fuel hoses, "
                    "and conduct continuous multi-gas sniffer test."
                ),
            )
        return None


class StopWorkAuthorityComplianceRule(BaseSafetyRule):
    """Enforces protocol when Stop Work Authority is invoked (prevents premature resumption)."""

    rule_id = "RULE-SWA-005"
    rule_name = "Premature Resumption After Stop Work Authority"
    severity = SeverityLevel.CRITICAL
    regulatory_standard = RegulatoryStandard.API_RP_54
    citation = "API RP 54 Section 4.3 & IADC SMS Policy (Stop Work Authority Lifecycle)"

    def evaluate(self, data: UnifiedSafetyData) -> Optional[RuleViolation]:
        if data.swa_invoked and data.premature_restart:
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                regulatory_standard=self.regulatory_standard,
                citation=self.citation,
                description=(
                    "Operations resumed after Stop Work Authority invocation without verified supervisor investigation, "
                    "root cause resolution, and formal safety restart sign-off."
                ),
                evidence=f"SWA Invoked: True, Premature Restart: True on Rig {data.rig_id}. Source: {data.source_id}",
                recommended_immediate_action=(
                    "Re-impose immediate rig shutdown on affected sub-system. Convene rig superintendent, safety lead, "
                    "and worker who invoked SWA for formal barrier sign-off."
                ),
            )
        return None


class HazardIsolationLOTORule(BaseSafetyRule):
    """Enforces positive energy isolation and Lockout/Tagout verification."""

    rule_id = "RULE-LOTO-006"
    rule_name = "Hazardous Energy Isolation (LOTO) Non-Conformance"
    severity = SeverityLevel.HIGH
    regulatory_standard = RegulatoryStandard.OSHA_1910_147
    citation = "29 CFR 1910.147 (Control of Hazardous Energy - Lockout/Tagout)"

    def evaluate(self, data: UnifiedSafetyData) -> Optional[RuleViolation]:
        if not data.lockout_tagout_verified or ("loto" in data.raw_text.lower() and "unisolated" in data.raw_text.lower()):
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                regulatory_standard=self.regulatory_standard,
                citation=self.citation,
                description=(
                    "Intervention or maintenance on energized machinery / pressurized piping occurred without documented "
                    "zero-energy verification, lock, tag, and bleed-down."
                ),
                evidence=f"LOTO Verified: {data.lockout_tagout_verified}. Raw text notes isolation discrepancy.",
                recommended_immediate_action=(
                    "Halt mechanical intervention, establish physical padlock and danger tag, dissipate stored pressure/gravity, "
                    "and perform try-step verification."
                ),
            )
        return None


class PersonalProtectiveEquipmentRule(BaseSafetyRule):
    """Enforces task-specific PPE adherence and pinch-point mitigation."""

    rule_id = "RULE-PPE-007"
    rule_name = "PPE & Hand Safety Barrier Omission"
    severity = SeverityLevel.MEDIUM
    regulatory_standard = RegulatoryStandard.OSHA_1910_132
    citation = "29 CFR 1910.132 (General PPE Requirements & Hand Protection)"

    def evaluate(self, data: UnifiedSafetyData) -> Optional[RuleViolation]:
        if data.ppe_compliance_gap or any("pinch point" in h.lower() for h in data.unmitigated_hazards):
            return RuleViolation(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                regulatory_standard=self.regulatory_standard,
                citation=self.citation,
                description=(
                    "Identified hand/body crush hazards or high-energy line manipulation without documented "
                    "impact glove specifications, push-poles, or hands-free line guiding tools."
                ),
                evidence=f"PPE Gap Flag: {data.ppe_compliance_gap}. Unmitigated items: {data.unmitigated_hazards}",
                recommended_immediate_action=(
                    "Provide certified ANSI Level 3+ impact gloves and push-pull tag lines. Revise JSA step to include hands-free policy."
                ),
            )
        return None
