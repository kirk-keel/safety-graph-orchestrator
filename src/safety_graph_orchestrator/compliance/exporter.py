from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from safety_graph_orchestrator.core.models import (
    CorrectiveActionReport,
    SeverityLevel,
)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Corrective Action Report - {car_number}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #1e293b;
            background-color: #f8fafc;
            margin: 0;
            padding: 40px;
        }}
        .container {{
            max-width: 960px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            padding: 40px;
            border: 1px solid #e2e8f0;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 20px;
            margin-bottom: 24px;
        }}
        .title-block h1 {{
            margin: 0;
            font-size: 24px;
            color: #0f172a;
            letter-spacing: -0.5px;
        }}
        .title-block p {{
            margin: 4px 0 0 0;
            color: #64748b;
            font-size: 14px;
        }}
        .badge {{
            display: inline-block;
            padding: 6px 14px;
            font-weight: 700;
            border-radius: 6px;
            font-size: 13px;
            text-transform: uppercase;
        }}
        .badge-CRITICAL {{ background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }}
        .badge-HIGH {{ background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; }}
        .badge-MEDIUM {{ background: #fefce8; color: #854d0e; border: 1px solid #fef08a; }}
        .badge-LOW {{ background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }}
        .badge-COMPLIANT {{ background: #f0fdf4; color: #15803d; border: 1px solid #86efac; }}
        .section {{
            margin-bottom: 32px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 700;
            color: #334155;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #cbd5e1;
            padding-bottom: 8px;
            margin-bottom: 14px;
        }}
        .executive-summary {{
            background: #f1f5f9;
            padding: 16px;
            border-left: 4px solid #3b82f6;
            border-radius: 4px;
            font-size: 15px;
            line-height: 1.6;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 14px;
        }}
        th, td {{
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background: #f8fafc;
            color: #475569;
            font-weight: 600;
        }}
        .tree-node {{
            background: #f8fafc;
            border-left: 3px solid #8b5cf6;
            padding: 10px 14px;
            margin-bottom: 8px;
            border-radius: 4px;
        }}
        .tree-level {{
            font-weight: 700;
            color: #6d28d9;
            font-size: 13px;
        }}
        .tree-answer {{
            margin-top: 4px;
            font-size: 14px;
            color: #1e293b;
        }}
        .signoff-box {{
            border: 2px dashed #94a3b8;
            border-radius: 6px;
            padding: 18px;
            background: #fafafa;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .footer {{
            margin-top: 40px;
            font-size: 12px;
            color: #94a3b8;
            text-align: center;
            border-top: 1px solid #e2e8f0;
            padding-top: 16px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title-block">
                <h1>CORRECTIVE ACTION REPORT (CAR / CAPA)</h1>
                <p>Report Number: <strong>{car_number}</strong> | Asset / Rig: <strong>{rig_id}</strong> | Generated: {generated_at}</p>
            </div>
            <div>
                <span class="badge badge-{severity_class}">{overall_severity}</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">1. Executive Summary & Regulatory Audit Scope</div>
            <div class="executive-summary">
                {executive_summary}
            </div>
            <p style="margin-top: 10px; font-size: 13px; color: #64748b;">
                <strong>Regulatory Standards Cited:</strong> {citations}
            </p>
        </div>

        {violations_html}

        {deliberation_html}

        {rca_html}

        <div class="section">
            <div class="section-title">CAPA Action Items (ISO 45001 / API Q2 Compliance)</div>
            <table>
                <thead>
                    <tr>
                        <th style="width: 100px;">Action ID</th>
                        <th style="width: 120px;">Type</th>
                        <th>Action Description</th>
                        <th style="width: 180px;">Responsible Party</th>
                        <th style="width: 100px;">Target</th>
                        <th>Verification Method</th>
                    </tr>
                </thead>
                <tbody>
                    {capa_rows}
                </tbody>
            </table>
        </div>

        <div class="section">
            <div class="section-title">Safety Governance & Sign-off Verification</div>
            <div class="signoff-box">
                <div>
                    <strong>Status:</strong> {audit_status}<br/>
                    <strong>Safety Director Sign-off Mandated:</strong> {director_signoff}<br/>
                    <strong>OSHA 300 / 301 Reportable Event:</strong> {osha_reportable}
                </div>
                <div style="text-align: right;">
                    <span class="badge badge-{severity_class}">VERIFIED AUDIT RECORD</span>
                </div>
            </div>
        </div>

        <div class="footer">
            Safety Graph Orchestrator • Stateful LangGraph Multi-Agent Safety System • OSHA / API RP 54 Compliance
        </div>
    </div>
</body>
</html>
"""


class ReportExporter:
    """Exports formal audit-ready Corrective Action Reports to HTML / PDF format."""

    @staticmethod
    def export_html(
        car: CorrectiveActionReport,
        output_path: Path,
    ) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        severity_class = car.overall_severity.value
        citations_str = ", ".join(car.regulatory_citations) if car.regulatory_citations else "API RP 54 / OSHA 1910"

        # Format violations
        if car.identified_violations:
            v_rows = []
            for v in car.identified_violations:
                v_rows.append(f"""
                <tr>
                    <td><strong>{v.rule_id}</strong></td>
                    <td><span class="badge badge-{v.severity.value}">{v.severity.value}</span></td>
                    <td><strong>{v.rule_name}</strong><br/>{v.description}</td>
                    <td>{v.citation}</td>
                    <td><em>{v.recommended_immediate_action}</em></td>
                </tr>
                """)
            violations_html = f"""
            <div class="section">
                <div class="section-title">2. Identified Safety Rule Violations ({len(car.identified_violations)})</div>
                <table>
                    <thead>
                        <tr>
                            <th>Rule ID</th>
                            <th>Severity</th>
                            <th>Violation Details</th>
                            <th>Citation</th>
                            <th>Immediate Action Required</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(v_rows)}
                    </tbody>
                </table>
            </div>
            """
        else:
            violations_html = """
            <div class="section">
                <div class="section-title">2. Deterministic Rule Evaluation</div>
                <p style="color: #166534; font-weight: 600;">Zero safety rule violations detected. Baseline operational procedures satisfied.</p>
            </div>
            """

        # Format Multi-Agent Deliberation
        deliberation_html = ""
        if car.root_cause_analysis and car.root_cause_analysis.deliberation_perspectives:
            d_rows = []
            for p in car.root_cause_analysis.deliberation_perspectives:
                findings = "<br/>".join([f"• {f}" for f in p.key_findings])
                d_rows.append(f"""
                <tr>
                    <td><strong>{p.agent_role}</strong></td>
                    <td>{findings}</td>
                    <td>{p.causal_assessment}</td>
                    <td>{p.recommended_focus}</td>
                </tr>
                """)
            deliberation_html = f"""
            <div class="section">
                <div class="section-title">3. Multi-Agent Deliberation Committee</div>
                <table>
                    <thead>
                        <tr>
                            <th>Domain Agent</th>
                            <th>Key Observations</th>
                            <th>Causal Assessment</th>
                            <th>Recommended Focus</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(d_rows)}
                    </tbody>
                </table>
            </div>
            """

        # Format 5 Whys RCA
        rca_html = ""
        if car.root_cause_analysis and car.root_cause_analysis.five_whys:
            rca = car.root_cause_analysis
            tree_nodes = []
            for step in rca.five_whys:
                tree_nodes.append(f"""
                <div class="tree-node">
                    <div class="tree-level">Level {step.level} Why: {step.question}</div>
                    <div class="tree-answer">↳ {step.answer} <span style="color: #64748b; font-size: 12px;">({step.causal_category.value})</span></div>
                </div>
                """)
            rca_html = f"""
            <div class="section">
                <div class="section-title">4. Arbiter Consensus & 5 Whys Root Cause Analysis</div>
                <p><strong>Direct Cause:</strong> {rca.direct_cause}</p>
                {''.join(tree_nodes)}
                <div style="background: #fdf4ff; border: 1px solid #f0abfc; padding: 12px; border-radius: 4px; margin-top: 10px;">
                    <strong>Systemic Root Cause Statement:</strong> {rca.root_cause_statement}
                </div>
            </div>
            """

        # Format CAPA items
        capa_rows = []
        for item in car.action_items:
            capa_rows.append(f"""
            <tr>
                <td><strong>{item.action_id}</strong></td>
                <td><span style="font-weight: 600; color: #4338ca;">{item.action_type}</span></td>
                <td>{item.description}</td>
                <td>{item.responsible_party}</td>
                <td>{item.target_completion_days} days</td>
                <td>{item.verification_method}</td>
            </tr>
            """)

        html_content = HTML_TEMPLATE.format(
            car_number=car.car_number,
            rig_id=car.rig_id,
            generated_at=car.generated_at,
            overall_severity=car.overall_severity.value,
            severity_class=severity_class,
            executive_summary=car.executive_summary,
            citations=citations_str,
            violations_html=violations_html,
            deliberation_html=deliberation_html,
            rca_html=rca_html,
            capa_rows="".join(capa_rows),
            audit_status=car.audit_status.value,
            director_signoff="Required" if car.requires_safety_director_signoff else "Not Required",
            osha_reportable="Yes (Mandatory 24-hr Notification)" if car.osha_reportable else "No",
        )

        output_path.write_text(html_content, encoding="utf-8")
        return output_path
