"""
Tests for Phase 6 Supervisor REST API & WebSocket Endpoint
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.risk.engine import process_situation_update, ACTIVE_SITUATIONS
from app.risk.models import SituationUpdate
from app.risk.incidents import get_incident_service

client = TestClient(app)


def test_list_incidents_and_detail_endpoint():
    ACTIVE_SITUATIONS.clear()
    session_id = "test_sup_sess_01"

    # Initially empty list or returns active incidents
    res = client.get("/api/incidents")
    assert res.status_code == 200

    # Process situation update
    process_situation_update(session_id, SituationUpdate(equipment="Machine 4", sparks=True))

    # GET /api/incidents should include session_id
    res = client.get("/api/incidents")
    assert res.status_code == 200
    incidents = res.json()
    assert any(i["session_id"] == session_id for i in incidents)

    # GET /api/incidents/{session_id}
    res_detail = client.get(f"/api/incidents/{session_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["session_id"] == session_id
    assert detail["severity"] == "CRITICAL"
    assert detail["situation"]["equipment"] == "Machine 4"
    assert detail["situation"]["sparks"] is True
    assert detail["situation"]["smoke"] is None  # explicit None preserved
    assert len(detail["audit_events"]) > 0


def test_supervisor_websocket_realtime_stream():
    ACTIVE_SITUATIONS.clear()
    session_id = "test_ws_sess_01"

    with client.websocket_connect("/ws/supervisor") as websocket:
        # Initial message should be sent
        initial = websocket.receive_json()
        assert initial["type"] == "initial_state"
        assert isinstance(initial["incidents"], list)

        # Trigger situation update
        process_situation_update(session_id, SituationUpdate(equipment="Machine 2", abnormal_vibration=True))

        # Check websocket broadcast message
        data = websocket.receive_json()
        assert data["type"] == "incident_updated"
        assert data["incident"]["session_id"] == session_id
        assert data["incident"]["severity"] == "MEDIUM"
        assert data["incident"]["situation"]["equipment"] == "Machine 2"
