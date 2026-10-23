from typing import Any, Dict, List

SEED_SAFETY_CORPUS: List[Dict[str, Any]] = [
    {
        "doc_id": "SOP-042",
        "title": "High-Pressure Choke Manifold Make-up and Pressure Testing",
        "category": "Well Control & Pressure Systems",
        "standard_reference": "API Spec 16D / API RP 54 Section 6",
        "content": (
            "Standard Operating Procedure SOP-042: High-Pressure Choke Manifold Make-up and Testing.\n"
            "1. Purpose: Governs the assembly, bolt-torquing sequence, and pressure integrity testing of surface choke manifolds (up to 15,000 PSI).\n"
            "2. Gasket Requirements: New BX-154 or API Spec 6A ring joint gaskets must be installed on every make-up. Re-use of metal ring gaskets is strictly prohibited.\n"
            "3. Torquing Protocol: A calibrated hydraulic torque wrench must be used. Hand-held pneumatic impact guns are strictly prohibited for final torque.\n"
            "4. Bolt Pattern: Torquing must be executed in a criss-cross star pattern in 3 stages: 30%, 70%, and 100% of final engineering torque.\n"
            "5. Pressure Test: Low-pressure test at 250-350 PSI for 5 minutes, followed by high-pressure test to maximum anticipated surface pressure (MASP) for 10 minutes with zero observable pressure drop.\n"
            "6. Stop Work Trigger: Any weeping, seepage, or audible pressure release mandates immediate bleed-off to 0 PSI and SWA invocation."
        ),
    },
    {
        "doc_id": "SOP-108",
        "title": "Derrick Monkey Board Working at Heights and Fall Arrest Systems",
        "category": "Working at Heights",
        "standard_reference": "29 CFR 1926.501 / API RP 54 Section 9.3",
        "content": (
            "Standard Operating Procedure SOP-108: Monkey Board and Derrick Height Safety.\n"
            "1. Scope: Applies to all operations on the mast, derrick racking board, monkey board, and stabbing board above 6 feet.\n"
            "2. Fall Protection Requirement: 100% tie-off is mandatory at all times. Personnel must be secured using a certified full-body harness with trauma relief straps and twin-tail energy-absorbing lanyards.\n"
            "3. Anchor Points: Anchor points must withstand a minimum static load of 5,000 lbs (22.2 kN) per employee.\n"
            "4. Pre-Use Inspection: Derrickman must inspect harness stitching, D-rings, carabiners, and self-retracting lifelines (SRLs) prior to ascending the mast. Any frayed webbing or impact indicators permanently decommission the gear.\n"
            "5. Weather Restrictions: Working on monkey board is prohibited if sustained winds exceed 40 knots, lightning is detected within 10 miles, or ice accumulation is present on railings."
        ),
    },
    {
        "doc_id": "SOP-215",
        "title": "Confined Space Entry and Mud Tank Atmospheric Testing",
        "category": "Toxic Gas & Confined Space",
        "standard_reference": "29 CFR 1910.146 / 29 CFR 1910.120",
        "content": (
            "Standard Operating Procedure SOP-215: Confined Space Entry in Active Mud Pits & Shaker Compartments.\n"
            "1. Permit Mandate: No employee shall enter a mud pit, reserve tank, or shaker sump without an active, signed Confined Space Entry Permit.\n"
            "2. Atmospheric Sniff Testing: Four-gas multi-detector test required prior to entry: Oxygen (19.5% - 23.5%), Flammable/Combustible (0% LEL), H2S (< 10 ppm), CO (< 25 ppm).\n"
            "3. Continuous Monitoring: Gas detector must remain calibrated, active, and worn in the breathing zone for the duration of the entry.\n"
            "4. Attendant Stationing: A dedicated, trained safety attendant must remain stationed outside the entryway with emergency retrieval winch and communication radio at all times.\n"
            "5. Ventilation: Positive forced mechanical ventilation must be running continuously for at least 15 minutes prior to initial entry and remain running throughout."
        ),
    },
    {
        "doc_id": "SOP-301",
        "title": "Tripping Pipe, Swabbing Prevention, and Well Barrier Monitoring",
        "category": "Well Control",
        "standard_reference": "API RP 54 Section 6.4 / IADC Well Control",
        "content": (
            "Standard Operating Procedure SOP-301: Tripping Pipe and Hole Fill Protocol.\n"
            "1. Swabbing Prevention: Hoisting speeds must be controlled to prevent piston swabbing and reducing bottom hole pressure below formation pore pressure.\n"
            "2. Trip Sheet Audit: A continuous trip tank volume monitoring sheet must be kept. Mud displacement must be calculated and verified every 5 stands of drill pipe.\n"
            "3. Inflow Detection: If the hole takes less mud than calculated displacement, tripping must halt immediately. Flow check must be conducted for a minimum of 10 minutes with pumps off.\n"
            "4. Well Barrier Gating: If flow check is positive (well flowing), the annular blowout preventer (BOP) must be closed immediately and well control kill sheet initiated.\n"
            "5. Drill Pipe Safety Valve: Full-opening safety valve (FOSV / TIW valve) in the open position with matching cross-over sub must be on the rig floor at all times."
        ),
    },
    {
        "doc_id": "SOP-504",
        "title": "Stop Work Authority (SWA) Protocol and Operational Resumption",
        "category": "Safety Management System (SMS)",
        "standard_reference": "API RP 54 Section 4.3 / ISO 45001",
        "content": (
            "Standard Operating Procedure SOP-504: Stop Work Authority Lifecycle.\n"
            "1. Universal Authority: Every employee and contractor on site has the absolute authority and obligation to halt any operation deemed unsafe without fear of retribution.\n"
            "2. Immediate Actions: When SWA is invoked, operations in the affected zone must immediately cease. Machinery must be brought to a safe idle or shutdown state.\n"
            "3. Notification: The person calling SWA must notify the rig superintendent and company HSE representative within 15 minutes.\n"
            "4. Root Cause & Remediation: The issue must be investigated, immediate containment applied, and systemic corrective actions identified.\n"
            "5. Resumption Gate: Operations may NOT resume until: (a) Physical condition is remediated and verified; (b) The person who called SWA agrees the hazard is eliminated; (c) Rig superintendent and HSE representative sign the written SWA close-out register. Bypassing this gate constitutes gross non-compliance."
        ),
    },
    {
        "doc_id": "OSHA-1910.120",
        "title": "OSHA 29 CFR 1910.120 - Toxic Gas and Emergency Response Contingency",
        "category": "Regulatory Compliance",
        "standard_reference": "29 CFR 1910.120 / OSHA H2S General Duty",
        "content": (
            "Federal Regulation 29 CFR 1910.120: Hazardous Waste Operations & Toxic Gas Exposure.\n"
            "1. Permissible Exposure Limit (PEL): Hydrogen Sulfide (H2S) acceptable ceiling concentration is 20 ppm; industry best practice standard is 10 ppm continuous action level.\n"
            "2. Alarm Setpoints: Low alarm at 10 ppm (amber visual strobe); High alarm at 20 ppm (audible siren + red strobe).\n"
            "3. Mandatory PPE: Positive-pressure Self-Contained Breathing Apparatus (SCBA) or supplied-air respirator with escape bottle required when H2S >= 10 ppm.\n"
            "4. Muster and Evacuation: All non-essential personnel must immediately evacuate cross-wind and up-wind to designated primary or secondary briefing areas upon alarm activation."
        ),
    },
    {
        "doc_id": "OSHA-1910.147",
        "title": "OSHA 29 CFR 1910.147 - Control of Hazardous Energy (Lockout/Tagout)",
        "category": "Regulatory Compliance",
        "standard_reference": "29 CFR 1910.147",
        "content": (
            "Federal Regulation 29 CFR 1910.147: Lockout/Tagout (LOTO).\n"
            "1. Objective: Prevent unexpected energization, start up, or release of stored energy during servicing and maintenance.\n"
            "2. Steps: (1) Preparation for shutdown; (2) Machine or equipment shutdown; (3) Machine isolation; (4) Lockout or tagout device application; (5) Stored energy dissipation (hydraulic bleed-down, mechanical pin, electrical discharge); (6) Verification of isolation (Try Step).\n"
            "3. Individual Protection: Each worker must apply their own personal lockout padlock and tag. Group lockout boxes require primary supervisor lock plus individual worker locks."
        ),
    },
    {
        "doc_id": "API-RP-54",
        "title": "API Recommended Practice 54 - Occupational Safety for Well Drilling and Servicing",
        "category": "Industry Standard",
        "standard_reference": "API Recommended Practice 54 (4th Edition)",
        "content": (
            "API RP 54 Standard for Well Drilling and Servicing Operations.\n"
            "1. Well Control: Choke manifold valves and high-pressure surface lines must be pressure tested periodically and documented in the official drilling log.\n"
            "2. Drilling Crew Pre-Spud & Pre-Job: Daily pre-tour safety meetings (JSA / tailgate) must be conducted and signed prior to commencing high-risk tasks.\n"
            "3. Derrick Work: Derricks and masts must be equipped with ladder safety devices or cages, and derrick climbing assists must be inspected per manufacturer specs.\n"
            "4. Fire Protection: Open fires, welding, or smoking are prohibited within 100 ft of wellbore or mud degassers unless authorized by formal Hot Work Permit."
        ),
    },
]
