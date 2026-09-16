"""
Decision 12 — Incident lifecycle tests A–O + idempotency.

Engine-driven tests use the module IncidentService (temp DB via conftest).
Service-level tests use a dedicated temp DB instance.
"""
import types

import pytest

from app.risk.engine import process_situation_update, ACTIVE_SITUATIONS
from app.risk.models import SituationUpdate
from app.risk.incidents import IncidentService, get_incident_service
import app.risk.incidents as incidents_module


@pytest.fixture
def service(tmp_path) -> IncidentService:
    return IncidentService(str(tmp_path / "incidents.db"))


def _critical_session(session_id: str = "sess_crit"):
    """Drive a session from empty to CRITICAL through the real engine."""
    ACTIVE_SITUATIONS.clear()
    process_situation_update(session_id, SituationUpdate(equipment="Machine 4"))
    process_situation_update(session_id, SituationUpdate(abnormal_vibration=True))
    process_situation_update(session_id, SituationUpdate(sparks=True))
    return session_id


def _critical_service_snap(session_id: str):
    return get_incident_service().get_snapshot(session_id)


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _FakeHTTPX:
    def __init__(self, result=_FakeResponse(200)):
        self.result = result
        self.calls = []

    def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


# ── A. CRITICAL detected → incident becomes CRITICAL ──────────────────────
def test_a_critical_detected_sets_incident_critical():
    session_id = _critical_session()
    snap = _critical_service_snap(session_id)
    assert snap["severity"] == "CRITICAL"
    assert snap["incident_status"] == "CRITICAL"
    assert snap["worker_safe"] is None
    assert snap["escalation_status"] == "not_escalated"


# ── B. CRITICAL → safety verification required ────────────────────────────
def test_b_critical_requires_safety_verification():
    session_id = _critical_session("sess_b")
    resp = process_situation_update(session_id, SituationUpdate(location="Zone A"))
    assert resp.severity == "CRITICAL"
    assert resp.next_question_goal == "Verify that the worker is safely away from the equipment"
    assert resp.priority == "critical"
    assert resp.immediate_actions == [
        "Move away from the equipment",
        "Do not touch or approach the equipment",
        "Stay clear of the affected area",
    ]
    events = get_incident_service().list_audit_events(session_id)
    event_types = [e["event_type"] for e in events]
    assert "critical_detected" in event_types
    assert "safety_instruction_given" in event_types
    assert "safety_verification_started" in event_types


# ── C. worker_safe=false → remains VERIFYING_SAFETY ────────────────────────
def test_c_worker_safe_false_stays_verifying():
    session_id = _critical_session("sess_c")
    svc = get_incident_service()
    result = svc.verify_worker_safety(session_id, False)
    assert result["incident_status"] == "VERIFYING_SAFETY"
    assert result["worker_safe"] is False

    escalated = svc.escalate_incident(session_id)
    assert escalated["status"] == "error"
    assert escalated["error"] == "escalation_requires_worker_safe"
    assert _critical_service_snap(session_id)["escalation_status"] == "not_escalated"

    event_types = [e["event_type"] for e in svc.list_audit_events(session_id)]
    assert "worker_safety_not_confirmed" in event_types
    assert "supervisor_notification_created" not in event_types
    assert "incident_escalated" not in event_types


# ── D. worker_safe=true → supervisor notification becomes eligible ─────────
def test_d_worker_safe_true_becomes_notification_eligible():
    session_id = _critical_session("sess_d")
    svc = get_incident_service()
    result = svc.verify_worker_safety(session_id, True)
    assert result["worker_safe"] is True
    # Verification alone does NOT escalate; the escalation workflow still has to run.
    assert result["incident_status"] == "CRITICAL"
    assert result["escalation_status"] == "not_escalated"
    event_types = [e["event_type"] for e in svc.list_audit_events(session_id)]
    assert "worker_safety_confirmed" in event_types


# ── E. notification succeeds → escalation becomes possible (simulated) ─────
def test_e_notification_created_then_escalation_possible():
    session_id = _critical_session("sess_e")
    svc = get_incident_service()
    svc.verify_worker_safety(session_id, True)
    n = svc.notify_supervisor(session_id)
    assert n["supervisor_notified"] is True
    assert n["supervisor_notification_status"] == "created"
    assert n["external_delivered"] is None  # simulated: record only, no external claim

    e = svc.escalate_incident(session_id)
    assert e["incident_status"] == "ESCALATED"
    assert e["escalation_status"] == "escalated"

    snaps = _critical_service_snap(session_id)
    assert snaps["severity"] == "CRITICAL"
    assert snaps["worker_safe"] is True
    assert snaps["supervisor_notified"] is True
    assert snaps["incident_status"] == "ESCALATED"


# ── F. notification FAILURE → no false claim of external delivery ──────────
def test_f_notification_failure_does_not_claim_delivery(monkeypatch):
    session_id = _critical_session("sess_f")

    # Point notify_supervisor at a failing webhook and stub httpx.post.
    from app.config import get_settings

    fake = _FakeHTTPX(_FakeResponse(500))
    monkeypatch.setattr(incidents_module.httpx, "post", fake.post)
    monkeypatch.setenv("SUPERVISOR_WEBHOOK_URL", "https://hooks.example.com/sentinel")
    get_settings.cache_clear()

    svc = get_incident_service()
    svc.verify_worker_safety(session_id, True)
    n = svc.notify_supervisor(session_id)
    assert n["supervisor_notified"] is True
    assert n["supervisor_notification_status"] == "failed"
    assert n["external_delivered"] is False
    assert len(fake.calls) == 1

    e = svc.escalate_incident(session_id)
    # Decision 5: a failed external delivery must not crash the workflow, and
    # the system must NOT claim the supervisor was actually contacted.
    assert e["incident_status"] == "ESCALATED"
    assert e["supervisor_notification_status"] == "failed"

    event_types = [ev["event_type"] for ev in svc.list_audit_events(session_id)]
    assert "supervisor_notification_failed" in event_types
    assert "supervisor_notification_delivered" not in event_types


# ── G. successful escalation → ESCALATED ────────────────────────────────────
def test_g_successful_escalation_full_state():
    session_id = _critical_session("sess_g")
    svc = get_incident_service()
    svc.verify_worker_safety(session_id, True)
    svc.notify_supervisor(session_id)
    final = svc.escalate_incident(session_id)
    assert final["incident_status"] == "ESCALATED"
    assert final["severity"] == "CRITICAL"
    assert final["worker_safe"] is True
    assert final["supervisor_notified"] is True
    assert final["escalation_status"] == "escalated"
    assert final["incident_id"]


# ── H. duplicate verification → idempotent ─────────────────────────────────
def test_h_duplicate_verification_idempotent():
    session_id = _critical_session("sess_h")
    svc = get_incident_service()
    svc.verify_worker_safety(session_id, True)
    again = svc.verify_worker_safety(session_id, True)
    assert again["worker_safe"] is True
    assert again["incident_status"] == "CRITICAL"

    event_types = [e["event_type"] for e in svc.list_audit_events(session_id)]
    assert event_types.count("worker_safety_confirmed") == 1


# ── I. duplicate notification → no duplicate records/re-fires ──────────────
def test_i_duplicate_notification_idempotent():
    session_id = _critical_session("sess_i")
    svc = get_incident_service()
    svc.verify_worker_safety(session_id, True)
    first = svc.notify_supervisor(session_id)
    second = svc.notify_supervisor(session_id)
    assert second["supervisor_notified"] is True
    assert second["status"] == "already_notified"
    assert second["supervisor_notification_status"] == first["supervisor_notification_status"]

    event_types = [e["event_type"] for e in svc.list_audit_events(session_id)]
    assert event_types.count("supervisor_notification_created") == 1


# ── J. duplicate escalation → idempotent ───────────────────────────────────
def test_j_duplicate_escalation_idempotent():
    session_id = _critical_session("sess_j")
    svc = get_incident_service()
    svc.verify_worker_safety(session_id, True)
    svc.notify_supervisor(session_id)
    first = svc.escalate_incident(session_id)
    second = svc.escalate_incident(session_id)
    assert second["status"] == "already_escalated"
    assert second["incident_status"] == first["incident_status"] == "ESCALATED"

    event_types = [e["event_type"] for e in svc.list_audit_events(session_id)]
    assert event_types.count("incident_escalated") == 1


# ── K. CRITICAL remains sticky ─────────────────────────────────────────────
def test_k_critical_remains_sticky():
    session_id = _critical_session("sess_k")
    resp = process_situation_update(session_id, SituationUpdate(people_nearby=2))
    assert resp.severity == "CRITICAL"
    assert resp.incident_status == "CRITICAL"


# ── L. unrelated updates do not downgrade CRITICAL ─────────────────────────
def test_l_unrelated_updates_do_not_downgrade():
    session_id = _critical_session("sess_l")
    snap_after = get_incident_service().get_snapshot(session_id)
    assert snap_after["incident_status"] == "CRITICAL"
    process_situation_update(session_id, SituationUpdate(location="Assembly Floor"))
    snap_final = get_incident_service().get_snapshot(session_id)
    assert snap_final["incident_status"] == "CRITICAL"


# ── M. LOW/MEDIUM never escalate ───────────────────────────────────────────
def test_m_low_medium_never_escalate():
    ACTIVE_SITUATIONS.clear()
    session_id = "sess_m"
    resp = process_situation_update(session_id, SituationUpdate(equipment="Machine 4"))
    assert resp.severity == "LOW"
    svc = get_incident_service()
    assert svc.get_snapshot(session_id)["incident_status"] == "INVESTIGATING"
    assert svc.escalate_incident(session_id)["error"] == "escalation_requires_critical"

    ACTIVE_SITUATIONS.clear()
    session_id = "sess_m2"
    process_situation_update(session_id, SituationUpdate(abnormal_vibration=True))
    assert svc.get_snapshot(session_id)["incident_status"] == "INVESTIGATING"
    assert svc.escalate_incident(session_id)["error"] == "escalation_requires_critical"


# ── N. invalid state transitions rejected ──────────────────────────────────
def test_n_invalid_transitions_rejected(service: IncidentService):
    assert service.verify_worker_safety("missing", True)["status"] == "error"
    assert service.notify_supervisor("missing")["status"] == "error"
    assert service.escalate_incident("missing")["status"] == "error"

    # CRITICAL but worker never confirmed → escalation blocked.
    session_id = _critical_session("sess_n")
    assert get_incident_service().escalate_incident(session_id)["error"] == "escalation_requires_worker_safe"

    # MEDIUM + worker_safe true must NOT escalate (severity gate is authoritative).
    ACTIVE_SITUATIONS.clear()
    sid = "sess_n2"
    process_situation_update(sid, SituationUpdate(abnormal_vibration=True))
    svc = get_incident_service()
    svc.verify_worker_safety(sid, True)
    assert svc.escalate_incident(sid)["error"] == "escalation_requires_critical"


# ── O. audit events created correctly ──────────────────────────────────────
def test_o_audit_events_created_correctly():
    session_id = _critical_session("sess_o")
    svc = get_incident_service()
    svc.verify_worker_safety(session_id, True)
    svc.notify_supervisor(session_id)
    svc.escalate_incident(session_id)

    events = svc.list_audit_events(session_id)
    expected = {
        "critical_detected",
        "safety_instruction_given",
        "safety_verification_started",
        "worker_safety_confirmed",
        "supervisor_notification_created",
        "incident_escalated",
    }
    assert expected.issubset({e["event_type"] for e in events})
    for ev in events:
        assert ev["incident_id"]
        assert ev["created_at"]

    from app.config import get_settings
    settings = get_settings()
    assert settings.supervisor_webhook_url == ""  # simulated mode by default
    assert "supervisor_notification_delivered" not in {e["event_type"] for e in events}


# ── Decision 5 — webhook DELIVERY success path ─────────────────────────────
def test_webhook_delivery_success_records_delivered(monkeypatch):
    from app.config import get_settings

    session_id = _critical_session("sess_webhook_ok")
    fake = _FakeHTTPX(_FakeResponse(200))
    monkeypatch.setattr(incidents_module.httpx, "post", fake.post)
    monkeypatch.setenv("SUPERVISOR_WEBHOOK_URL", "https://hooks.example.com/sentinel")
    get_settings.cache_clear()

    svc = get_incident_service()
    svc.verify_worker_safety(session_id, True)
    n = svc.notify_supervisor(session_id)
    assert n["supervisor_notification_status"] == "delivered"
    assert n["external_delivered"] is True
    assert n["supervisor_notified"] is True
    assert np_payload(fake)["severity"] == "CRITICAL"

    event_types = [e["event_type"] for e in svc.list_audit_events(session_id)]
    assert "supervisor_notification_delivered" in event_types
    assert "supervisor_notification_failed" not in event_types


def np_payload(fake: _FakeHTTPX) -> dict:
    assert fake.calls, "webhook POST was never called"
    _, kwargs = fake.calls[0]
    return kwargs["json"]