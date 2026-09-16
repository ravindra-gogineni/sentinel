"""
SENTINEL Backend — Supervisor API Router & WebSocket Endpoint (Phase 6)
"""
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Path, WebSocket, WebSocketDisconnect

from app.risk.incidents import get_incident_service
from app.risk.engine import ACTIVE_SITUATIONS
from app.risk.risk_engine import calculate_severity
from app.api.broadcaster import connection_manager

router = APIRouter(prefix="/api/incidents", tags=["supervisor"])
ws_router = APIRouter(tags=["supervisor_ws"])


def build_full_incident_detail(session_id: str) -> Optional[Dict[str, Any]]:
    """Builds comprehensive incident state payload for dashboard visualization."""
    svc = get_incident_service()
    snapshot = svc.get_snapshot(session_id)
    if not snapshot:
        return None

    situation = ACTIVE_SITUATIONS.get(session_id)
    situation_data = situation.model_dump() if situation else {"session_id": session_id}
    
    # Calculate risk from situation model if available
    risk_data = {"severity": snapshot.get("severity", "LOW"), "reasons": [], "immediate_actions": []}
    if situation:
        risk_assessment = calculate_severity(situation)
        risk_data = risk_assessment.model_dump()

    audit_events = svc.list_audit_events(session_id)

    return {
        "session_id": session_id,
        "incident_id": snapshot.get("incident_id"),
        "incident_status": snapshot.get("incident_status"),
        "severity": snapshot.get("severity"),
        "worker_safe": snapshot.get("worker_safe"),
        "supervisor_notified": snapshot.get("supervisor_notified"),
        "supervisor_notification_status": snapshot.get("supervisor_notification_status"),
        "escalation_status": snapshot.get("escalation_status"),
        "situation": situation_data,
        "risk": risk_data,
        "audit_events": audit_events,
    }


@router.get("", response_model=List[Dict[str, Any]])
async def list_active_incidents() -> List[Dict[str, Any]]:
    """Returns all active incident snapshots with full state for the supervisor dashboard."""
    incidents = []
    # Collect all known sessions from ACTIVE_SITUATIONS or SQLite
    svc = get_incident_service()
    session_ids = set(ACTIVE_SITUATIONS.keys())
    
    # Also fetch sessions from DB in case service was reloaded
    conn = svc._connect()
    try:
        rows = conn.execute("SELECT session_id FROM incidents").fetchall()
        for r in rows:
            session_ids.add(r["session_id"])
    finally:
        conn.close()

    for sid in session_ids:
        detail = build_full_incident_detail(sid)
        if detail:
            incidents.append(detail)

    return incidents


@router.get("/{session_id}", response_model=Dict[str, Any])
async def get_incident_detail(
    session_id: str = Path(..., description="AssemblyAI session ID")
) -> Dict[str, Any]:
    """Returns full incident details, situation facts, risk reasons, and audit timeline."""
    detail = build_full_incident_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Incident not found")
    return detail


@ws_router.websocket("/ws/supervisor")
async def supervisor_websocket(websocket: WebSocket) -> None:
    """Real-time WebSocket endpoint streaming live incident updates to supervisor dashboards."""
    await connection_manager.connect(websocket)
    try:
        # Send initial snapshot of all active incidents upon connect
        incidents = []
        svc = get_incident_service()
        session_ids = set(ACTIVE_SITUATIONS.keys())
        conn = svc._connect()
        try:
            rows = conn.execute("SELECT session_id FROM incidents").fetchall()
            for r in rows:
                session_ids.add(r["session_id"])
        finally:
            conn.close()

        for sid in session_ids:
            detail = build_full_incident_detail(sid)
            if detail:
                incidents.append(detail)

        await websocket.send_json({
            "type": "initial_state",
            "incidents": incidents
        })

        # Keep connection open for incoming messages / heartbeats
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as exc:
        connection_manager.disconnect(websocket)
