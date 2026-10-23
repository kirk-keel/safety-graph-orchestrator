from pathlib import Path

from safety_graph_orchestrator.core.checkpoint import get_sqlite_checkpointer
from safety_graph_orchestrator.core.models import AuditStatus, InputType
from safety_graph_orchestrator.graph.builder import (
    build_safety_graph,
    review_escalated_audit,
    run_safety_audit,
)


def test_sqlite_checkpoint_and_hitl_signoff(tmp_path: Path, swa_manifold_payload: str):
    db_file = tmp_path / "test_checkpoints.db"
    checkpointer = get_sqlite_checkpointer(db_file)
    graph = build_safety_graph(checkpointer=checkpointer)

    thread_id = "test-thread-hitl-001"

    # Step 1: Run audit on SWA payload (triggers escalation)
    final_state = run_safety_audit(
        raw_input=swa_manifold_payload,
        input_type=InputType.SWA,
        thread_id=thread_id,
        graph=graph,
    )

    assert final_state["status"] == AuditStatus.ESCALATED_TO_HUMAN
    assert final_state["human_approval"] == "AWAITING_HSE_DIRECTOR_REVIEW"

    # Verify SQLite file was populated
    assert db_file.exists()

    # Step 2: Safety Director reviews and approves the remediation
    resolved_state = review_escalated_audit(
        thread_id=thread_id,
        approved=True,
        reviewer_name="Jane Doe, VP Health & Safety",
        comments="Choke manifold isolated and torqued with hydraulic unit BX-154. Approved to resume.",
        graph=graph,
    )

    assert resolved_state["human_approval"] == "APPROVED"
    assert resolved_state["status"] == AuditStatus.COMPLETED
    assert resolved_state["car_report"].audit_status == AuditStatus.COMPLETED

    # Verify audit log includes human review entry
    last_log = resolved_state["audit_log"][-1]
    assert last_log.node_name == "human_review_gate"
    assert "APPROVED" in last_log.action


def test_sqlite_checkpoint_hitl_rejection(tmp_path: Path, swa_manifold_payload: str):
    db_file = tmp_path / "test_checkpoints_reject.db"
    checkpointer = get_sqlite_checkpointer(db_file)
    graph = build_safety_graph(checkpointer=checkpointer)

    thread_id = "test-thread-hitl-002"

    run_safety_audit(
        raw_input=swa_manifold_payload,
        input_type=InputType.SWA,
        thread_id=thread_id,
        graph=graph,
    )

    # Safety Director rejects incomplete remediation
    rejected_state = review_escalated_audit(
        thread_id=thread_id,
        approved=False,
        reviewer_name="John Smith, Rig Safety Lead",
        comments="H2S monitor recalibration cert not provided. Restart rejected.",
        graph=graph,
    )

    assert rejected_state["human_approval"] == "REJECTED"
    assert rejected_state["status"] == AuditStatus.REJECTED
    assert rejected_state["car_report"].audit_status == AuditStatus.REJECTED
