# Safety Standards & Regulatory Compliance Taxonomy

The Safety Graph Orchestrator enforces rigorous compliance with federal regulations and oilfield safety standards.

---

## 1. Regulatory Standards Coverage

### OSHA 29 CFR 1910.120 (HAZWOPER / Toxic Gas Contingency)
- **Mandate**: Employers must implement engineering controls, active continuous gas monitoring, and emergency response procedures when handling toxic gases such as Hydrogen Sulfide ($H_2S$).
- **Trigger Threshold**: Continuous concentration $\ge 10\text{ ppm}$.
- **Orchestrator Enforcement**:
  - Gated by `H2SToxicGasRule` (`RULE-H2S-001`).
  - Flags mandatory 30-minute positive-pressure SCBA donning, muster upwind, and immediate evacuation.
  - Automatically tags CAR as **OSHA Reportable**.

### OSHA 29 CFR 1910.147 (Control of Hazardous Energy - Lockout/Tagout)
- **Mandate**: Isolation of mechanical, electrical, hydraulic, and pneumatic energy sources before maintenance or servicing.
- **Orchestrator Enforcement**:
  - Gated by `LockoutTagoutRule` (`RULE-LOTO-004`).
  - Prohibits maintenance work without verified zero-energy state documentation and personal padlock application.

### OSHA 29 CFR 1926.501 (Fall Protection Systems)
- **Mandate**: Mandatory personal fall arrest systems (PFAS), guardrails, or safety nets for work at elevations of 6 feet or higher.
- **Orchestrator Enforcement**:
  - Gated by `WorkingAtHeightsRule` (`RULE-FALLPROT-003`).
  - Detects operations on the monkey board, derrick, or rig floor without dual 100% tie-off or certified anchor points.

### OSHA 29 CFR 1910.119 (Process Safety Management)
- **Mandate**: Safe conduct of hot work (welding, cutting, grinding) in proximity to flammable hydrocarbons.
- **Orchestrator Enforcement**:
  - Gated by `HotWorkPermitRule` (`RULE-HOTWORK-006`).
  - Checks lower explosive limit (LEL) readings ($\ge 10\%$) and active hot work permits.

### API RP 54 (Recommended Practice for Health and Safety in Well Drilling)
- **Section 4.3 (Stop Work Authority)**:
  - Grants every worker the obligation and authority to stop work when an unsafe condition arises.
  - Mandates that work **shall not resume** without documented supervisor approval and verification of safe conditions.
  - Orchestrator Enforcement: `SWAPrematureRestartRule` (`RULE-SWA-005`).
- **Section 6 (Well Control & Choke Manifold Integrity)**:
  - Mandates redundant barriers and continuous integrity verification on choke and kill manifolds.

### API Spec 16D (Control Systems for Drilling Well Control Equipment)
- **Mandate**: Standards for blowout prevention (BOP) control systems, pressure testing, and hydraulic isolation valves.
- **Orchestrator Enforcement**: `WellControlBarrierRule` (`RULE-WELLCTRL-002`).

---

## 2. Corrective Action Framework (ISO 45001 & API Q2)

The orchestrator structures all recommendations following the closed-loop **CAPA (Corrective and Preventive Action)** hierarchy:

```
+-----------------------------------------------------------------------------+
|                          1. Immediate Containment                           |
|  - Isolate active hazardous lines (hydraulic gate valve / LOTO)             |
|  - Bleed line pressure to 0 PSI                                             |
|  - Evacuate affected zone / establish safety perimeter                      |
|  - Target: Within 24 hours (1 Day)                                          |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                          2. Corrective Remediation                          |
|  - Replace damaged seals / gaskets with certified OEM components           |
|  - Conduct torque audit using calibrated hydraulic torque wrenches         |
|  - Re-certify hydrostatic pressure test per API RP 53 / 16D                |
|  - Target: 3 to 7 Days                                                      |
+-----------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------+
|                          3. Preventive Systems Fix                          |
|  - Update Standard Operating Procedures (SOP-042 / SOP-015)                 |
|  - Implement digital supervisory sign-off gates in tour sheets             |
|  - Conduct rig-wide safety stand-down on shift handover & SWA verification  |
|  - Target: 30 Days                                                          |
+-----------------------------------------------------------------------------+
```
