"""
Decision 13 — Programmatic end-to-end backend test.

Proves the full Phase 5 chain without any AssemblyAI credits:

  severity   LOw -> MEDIUM -> HIGH -> CRITICAL   (risk engine, sticky)
  worker_safe None -> True                        (verify_worker_safety)
  supervisor notification recorded                (notify_supervisor)
  incident escalated                              (escalate_incident)
"""
from app.risk.engine import process_situation_update, ACTIVE_SITUATIONS
from app.risk.models import SituationUpdate
from app.risk.incidents import get_incident_service


def test_phase5_end_to_end_backend():
    ACTIVE_SITUATIONS.clear()
    svc = get_incident_service()
    session_id = "sess_e2e"

    # ── Initial: LOW / null / INVESTIGATING ──────────────────────────────
    r = process_situation_update(session_id, SituationUpdate(equipment="Machine 4"))
    assert r.severity == "LOW"
    assert r.worker_safe is None
    assert r.incident_status == "INVESTIGATING"

    # ── abnormal_vibration → MEDIUM ──────────────────────────────────────
    r = process_situation_update(session_id, SituationUpdate(abnormal_vibration=True))
    assert r.severity == "MEDIUM"

    # ── machine_running + vibration_increasing → HIGH ────────────────────
    r = process_situation_update(
        session_id,
        SituationUpdate(machine_running=True, vibration_increasing=True),
    )
    assert r.severity == "HIGH"

    # ── sparks → CRITICAL / status CRITICAL / worker_safe null ───────────
    r = process_situation_update(session_id, SituationUpdate(sparks=True))
    assert r.severity == "CRITICAL"
    assert r.incident_status == "CRITICAL"
    assert r.worker_safe is None
    assert r.immediate_actions == [
        "Move away from the equipment",
        "Do not touch or approach the equipment",
        "Stay clear of the affected area",
    ]

    # ── verify_worker_safety(true) → worker_safe = true ───────────────────
    v = svc.verify_worker_safety(session_id, True)
    assert v["worker_safe"] is True
    assert v["incident_status"] == "CRITICAL"

    # ── notify_supervisor → notification recorded ─────────────────────────
    n = svc.notify_supervisor(session_id)
    assert n["supervisor_notified"] is True

    # ── escalate_incident → status ESCALATED ──────────────────────────────
    e = svc.escalate_incident(session_id)
    assert e["incident_status"] == "ESCALATED"

    # ── Final snapshot ────────────────────────────────────────────────────
    final = svc.get_snapshot(session_id)
    assert final["severity"] == "CRITICAL"
    assert final["worker_safe"] is True
    assert final["supervisor_notified"] is True
    assert final["incident_status"] == "ESCALATED"
    assert final["escalation_status"] == "escalated"
    assert final["incident_id"]

    # Audit trail captures the milestone events in order.
    events = [a["event_type"] for a in svc.list_audit_events(session_id)]
    milestones = [
        "critical_detected",
        "safety_instruction_given",
        "safety_verification_started",
        "worker_safety_confirmed",
        "supervisor_notification_created",
        "incident_escalated",
    ]
    idx = -1
    for m in milestones:
        idx = events.index(m, idx + 1)  # strict order
    assert idx >= 0