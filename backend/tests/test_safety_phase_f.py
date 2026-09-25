import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.risk.incidents import get_incident_service
from app.risk.engine import ACTIVE_SITUATIONS

# Set raise_server_exceptions=False so 500 errors can be tested correctly
client = TestClient(app, raise_server_exceptions=False)

@pytest.fixture(autouse=True)
def clear_active_situations():
    ACTIVE_SITUATIONS.clear()
    yield
    ACTIVE_SITUATIONS.clear()

def test_validation_error_handler_returns_422_json():
    """
    Tests that a missing field in the request payload returns our custom
    structured JSON format, rather than the default FastAPI unhandled format,
    while correctly maintaining the 422 status code.
    """
    session_id = "test_sess_422"
    # The payload requires {"safe": bool}. We send an empty dict.
    response = client.post(f"/api/verify/{session_id}", json={})
    
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "error"
    assert data["error"] == "invalid_payload"
    assert "safe" in data["details"][0]

def test_global_exception_handler_returns_500_json(monkeypatch):
    """
    Tests that an unhandled Exception within an endpoint is caught by the
    global exception handler, logged securely, and returns a 500 JSON
    without leaking internal stack traces.
    """
    def mock_verify_error(*args, **kwargs):
        raise ValueError("Internal DB corruption (mocked)")

    monkeypatch.setattr("app.risk.incidents.IncidentService.verify_worker_safety", mock_verify_error)
    
    session_id = "test_sess_500"
    response = client.post(f"/api/verify/{session_id}", json={"safe": True})
    
    assert response.status_code == 500
    data = response.json()
    assert data["status"] == "error"
    assert data["error"] == "internal_server_error"
    assert "An unexpected error occurred" in data["message"]
    assert "Internal DB corruption" not in str(data)

def test_incident_lifecycle_and_idempotency_phase_f():
    """
    Tests the complete incident lifecycle ensuring sticky critical states,
    idempotent verification/escalation, and comprehensive audit trails.
    """
    session_id = "test_sess_lifecycle"
    
    # 1. Trigger CRITICAL incident via SituationUpdate
    update_res = client.post(
        f"/api/situation/{session_id}",
        json={
            "observation": "There are massive sparks and smoke everywhere!",
            "sparks": True,
            "smoke": True,
            "machine_running": True
        }
    )
    assert update_res.status_code == 200
    data = update_res.json()
    assert data["severity"] == "CRITICAL"
    assert data["incident_status"] == "CRITICAL"
    assert data["worker_safe"] is None
    
    # 2. Verify worker safety (Not Safe) -> VERIFYING_SAFETY
    verify_res1 = client.post(
        f"/api/verify/{session_id}",
        json={"safe": False}
    )
    assert verify_res1.status_code == 200
    assert verify_res1.json()["incident_status"] == "VERIFYING_SAFETY"
    
    # 3. Repeated Verification (Idempotent)
    verify_res2 = client.post(
        f"/api/verify/{session_id}",
        json={"safe": False}
    )
    assert verify_res2.status_code == 200
    assert verify_res2.json()["incident_status"] == "VERIFYING_SAFETY"
    
    # 4. Verify worker safety (Safe) -> ESCALATED
    verify_res3 = client.post(
        f"/api/verify/{session_id}",
        json={"safe": True}
    )
    assert verify_res3.status_code == 200
    assert verify_res3.json()["incident_status"] == "ESCALATED"
    
    # 5. Repeated Escalation Verification (Idempotent)
    verify_res4 = client.post(
        f"/api/verify/{session_id}",
        json={"safe": True}
    )
    assert verify_res4.status_code == 200
    assert verify_res4.json()["incident_status"] == "ESCALATED"
    
    # 6. Critical State Downgrade Prevention
    # Try updating the situation with harmless facts
    update_res2 = client.post(
        f"/api/situation/{session_id}",
        json={"observation": "Actually it was just a false alarm, everything is normal."}
    )
    assert update_res2.status_code == 200
    # Incident status MUST remain ESCALATED
    assert update_res2.json()["incident_status"] == "ESCALATED"
    
    # 7. Verify Audit Trail creation
    svc = get_incident_service()
    events = svc.list_audit_events(session_id)
    event_types = [e["event_type"] for e in events]
    
    assert "critical_detected" in event_types
    assert "worker_safety_not_confirmed" in event_types
    assert "worker_safety_confirmed" in event_types
    assert "incident_escalated" in event_types
    
    # Check that idempotent calls did not duplicate audit events
    assert event_types.count("worker_safety_not_confirmed") == 1
    assert event_types.count("worker_safety_confirmed") == 1
    assert event_types.count("incident_escalated") == 1
