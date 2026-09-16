"""
SENTINEL Backend — Incident Lifecycle Service (Phase 5)

Owns the ONLY sqlite usage in the application. All sqlite calls are isolated here.

Lifecycle: INVESTIGATING -> CRITICAL -> VERIFYING_SAFETY -> ESCALATED

worker_safe (None/False/True) is a FACT/field, not an incident status. The backend
is authoritative: the AssemblyAI agent only reports { safe: true|false } through a
structured tool call; the LLM can never decide escalation on its own.

Idempotency:
  - verify_worker_safety()  repeated with the same value -> no conflicting state,
                            no duplicate audit event.
  - notify_supervisor()     second call returns the existing notification, never
                            re-fires or duplicates records.
  - escalate_incident()     once ESCALATED, further calls are no-ops.
"""
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings
from app.risk.response import determine_response_stage, verification_guidance

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    session_id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'INVESTIGATING',
    severity TEXT NOT NULL DEFAULT 'LOW',
    worker_safe INTEGER,
    supervisor_notified INTEGER NOT NULL DEFAULT 0,
    supervisor_notification_status TEXT NOT NULL DEFAULT 'not_configured',
    escalation_status TEXT NOT NULL DEFAULT 'not_escalated',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT,
    session_id TEXT,
    event_type TEXT NOT NULL,
    source TEXT,
    details TEXT,
    created_at TEXT NOT NULL
);
"""

_INCIDENT_FIELDS = (
    "incident_id",
    "incident_status",
    "severity",
    "worker_safe",
    "supervisor_notified",
    "supervisor_notification_status",
    "escalation_status",
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_incident_id() -> str:
    return "INC-" + uuid.uuid4().hex[:10].upper()


def _opt_bool(value: Optional[bool]) -> Optional[int]:
    if value is None:
        return None
    return 1 if value else 0


def _as_bool(value: Optional[int]) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


class IncidentService:
    """State machine + persistence + notification + audit for a single incident flow."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_settings().sentinel_db_path
        self._init_schema()

    # ── Low-level persistence (isolated here) ─────────────────────────────
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _append_audit(
        self,
        conn: sqlite3.Connection,
        incident_id: str,
        session_id: str,
        event_type: str,
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        conn.execute(
            "INSERT INTO audit_events (incident_id, session_id, event_type, source, details, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                incident_id,
                session_id,
                event_type,
                source,
                json.dumps(details) if details else None,
                _utcnow(),
            ),
        )

    def _row_to_snapshot(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "incident_id": row["incident_id"],
            "incident_status": row["status"],
            "severity": row["severity"],
            "worker_safe": _as_bool(row["worker_safe"]),
            "supervisor_notified": bool(row["supervisor_notified"]),
            "supervisor_notification_status": row["supervisor_notification_status"],
            "escalation_status": row["escalation_status"],
        }

    def _get_row(self, conn: sqlite3.Connection, session_id: str) -> Optional[sqlite3.Row]:
        return conn.execute(
            "SELECT * FROM incidents WHERE session_id = ?", (session_id,)
        ).fetchone()

    def _fetch_row(self, session_id: str) -> Optional[sqlite3.Row]:
        """Read a row with a short-lived connection that is closed immediately."""
        conn = self._connect()
        try:
            return self._get_row(conn, session_id)
        finally:
            conn.close()

    # ── Public API ─────────────────────────────────────────────────────────
    def sync_incident(
        self,
        session_id: str,
        severity: str,
        worker_safe: Optional[bool],
        immediate_actions: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Called from the risk engine after every situation update. Keeps the
        persisted incident row aligned with the current severity + worker fact.
         * Creates the incident row on first sighting.
         * Emits transition audit events exactly once per transition.
         * Never auto-escalates: ESCALATED is reached only through
           escalate_incident() after the notification workflow.
        """
        immediate_actions = list(immediate_actions or [])
        conn = self._connect()
        try:
            row = self._get_row(conn, session_id)
            if row is None:
                incident_id = _generate_incident_id()
                status = determine_response_stage(None, severity, worker_safe)
                conn.execute(
                    "INSERT INTO incidents "
                    "(session_id, incident_id, status, severity, worker_safe, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        incident_id,
                        status,
                        severity,
                        _opt_bool(worker_safe),
                        _utcnow(),
                        _utcnow(),
                    ),
                )
                self._emit_transition_events(
                    conn, incident_id, session_id, None, status, immediate_actions
                )
                conn.commit()
                return self._row_to_snapshot(
                    self._get_row(conn, session_id)
                )

            prev_status = row["status"]
            merged_worker = worker_safe if worker_safe is not None else _as_bool(row["worker_safe"])
            derived = determine_response_stage(prev_status, severity, merged_worker)

            if derived == "ESCALATED" and not bool(row["supervisor_notified"]):
                # Eligibility reached, but notification workflow has not run yet.
                # Hold at the critical flow until escalate_incident() handles it.
                derived = prev_status if prev_status in ("CRITICAL", "VERIFYING_SAFETY") else "CRITICAL"

            conn.execute(
                "UPDATE incidents SET status = ?, severity = ?, worker_safe = ?, updated_at = ? "
                "WHERE session_id = ?",
                (derived, severity, _opt_bool(merged_worker), _utcnow(), session_id),
            )
            if prev_status != derived:
                self._emit_transition_events(
                    conn, row["incident_id"], session_id, prev_status, derived, immediate_actions
                )
            conn.commit()
            return self._row_to_snapshot(self._get_row(conn, session_id))
        finally:
            conn.close()

    def verify_worker_safety(self, session_id: str, safe: bool) -> Dict[str, Any]:
        """
        Backend-authoritative safety confirmation. Agent reports { safe: bool }
        via the verify_worker_safety tool; the backend decides the consequences.

        safe=True   -> sets the worker_safe FACT and leaves the incident at
                       CRITICAL so the escalation workflow (notify -> escalate)
                       can run explicitly.
        safe=False  -> incident moves to VERIFYING_SAFETY; no escalation.
        """
        conn = self._connect()
        try:
            row = self._get_row(conn, session_id)
            if row is None:
                return {
                    "status": "error",
                    "error": "incident_not_found",
                    "session_id": session_id,
                }

            prev_worker = _as_bool(row["worker_safe"])

            if row["status"] == "ESCALATED":
                # Idempotent: already escalated, keep it there.
                new_status = "ESCALATED"
            elif row["severity"] != "CRITICAL":
                new_status = "INVESTIGATING"
            elif safe:
                new_status = "CRITICAL"
            else:
                new_status = "VERIFYING_SAFETY"

            # Idempotency: audit the confirmation only when the fact CHANGES.
            if prev_worker != safe:
                event = "worker_safety_confirmed" if safe else "worker_safety_not_confirmed"
                self._append_audit(
                    conn,
                    row["incident_id"],
                    session_id,
                    event,
                    source="verify_worker_safety",
                    details={"safe": safe},
                )

            conn.execute(
                "UPDATE incidents SET worker_safe = ?, status = ?, updated_at = ? WHERE session_id = ?",
                (_opt_bool(safe), new_status, _utcnow(), session_id),
            )
            conn.commit()
            snapshot = self._row_to_snapshot(self._get_row(conn, session_id))
            snapshot["status"] = "verified" if safe else "not_confirmed"
            return snapshot
        finally:
            conn.close()

    def notify_supervisor(self, session_id: str) -> Dict[str, Any]:
        """
        Application-level supervisor notification (prototype):
         * Always creates the notification record + audit event (supervisor_notified=True).
         * If SUPERVISOR_WEBHOOK_URL is configured, POSTs a structured payload; the
           delivery result is recorded without ever crashing the incident workflow.
         * If unconfigured, logs a SIMULATED notification (never claims external delivery).
        Idempotent: a second call returns the existing notification unchanged.
        """
        conn = self._connect()
        try:
            row = self._get_row(conn, session_id)
            if row is None:
                return {
                    "status": "error",
                    "error": "incident_not_found",
                    "session_id": session_id,
                }

            if bool(row["supervisor_notified"]):
                snapshot = self._row_to_snapshot(row)
                snapshot["status"] = "already_notified"
                return snapshot

            settings = get_settings()
            webhook_url = (settings.supervisor_webhook_url or "").strip()

            conn.execute(
                "UPDATE incidents SET supervisor_notified = 1, "
                "supervisor_notification_status = 'created', updated_at = ? WHERE session_id = ?",
                (_utcnow(), session_id),
            )
            self._append_audit(
                conn,
                row["incident_id"],
                session_id,
                "supervisor_notification_created",
                source="notify_supervisor",
                details={
                    "webhook_configured": bool(webhook_url),
                    "mode": "webhook" if webhook_url else "simulated",
                },
            )
            conn.commit()

            delivered: Optional[bool] = None
            notification_status = "created"

            if webhook_url:
                payload = self._notification_payload(
                    row["incident_id"], session_id, row["severity"], _as_bool(row["worker_safe"])
                )
                try:
                    resp = httpx.post(webhook_url, json=payload, timeout=5.0)
                    delivered = resp.status_code < 400
                    details = {
                        "url": webhook_url,
                        "status_code": resp.status_code,
                        "ok": delivered,
                    }
                except Exception as exc:  # noqa: BLE001 — external delivery must never crash the flow
                    logger.exception("Supervisor webhook POST failed: %s", exc)
                    delivered = False
                    details = {"url": webhook_url, "error": str(exc), "ok": False}

                notification_status = "delivered" if delivered else "failed"
                event = (
                    "supervisor_notification_delivered"
                    if delivered
                    else "supervisor_notification_failed"
                )
                conn.execute(
                    "UPDATE incidents SET supervisor_notification_status = ?, updated_at = ? "
                    "WHERE session_id = ?",
                    (notification_status, _utcnow(), session_id),
                )
                self._append_audit(
                    conn, row["incident_id"], session_id, event,
                    source="notify_supervisor", details=details,
                )
                conn.commit()
            else:
                logger.info(
                    "[SENTINEL] Simulated supervisor notification for %s (no SUPERVISOR_WEBHOOK_URL)",
                    session_id,
                )

            snapshot = self._row_to_snapshot(self._get_row(conn, session_id))
            snapshot["status"] = "notification_created"
            snapshot["external_delivered"] = delivered
            return snapshot
        finally:
            conn.close()

    def escalate_incident(self, session_id: str) -> Dict[str, Any]:
        """
        Backend-authoritative escalation. Requirements (both enforced here):
          severity == CRITICAL AND worker_safe is True.
        Runs the supervisor-notification workflow first (idempotent) when the
        record does not exist yet. Idempotent: ESCALATED stays ESCALATED.
        """
        found = self._fetch_row(session_id)
        if found is None:
            return {
                "status": "error",
                "error": "incident_not_found",
                "session_id": session_id,
            }

        if found["status"] == "ESCALATED":
            snapshot = self._row_to_snapshot(found)
            snapshot["status"] = "already_escalated"
            return snapshot

        if found["severity"] != "CRITICAL":
            return {
                "status": "error",
                "error": "escalation_requires_critical",
                "incident_id": found["incident_id"],
            }
        if _as_bool(found["worker_safe"]) is not True:
            return {
                "status": "error",
                "error": "escalation_requires_worker_safe",
                "incident_id": found["incident_id"],
            }

        # Notification workflow must run (or have run) before escalation.
        if not bool(found["supervisor_notified"]):
            self.notify_supervisor(session_id)

        conn = self._connect()
        try:
            row = self._get_row(conn, session_id)
            conn.execute(
                "UPDATE incidents SET status = 'ESCALATED', escalation_status = 'escalated', "
                "updated_at = ? WHERE session_id = ?",
                (_utcnow(), session_id),
            )
            self._append_audit(
                conn,
                row["incident_id"],
                session_id,
                "incident_escalated",
                source="escalate_incident",
                details={
                    "severity": row["severity"],
                    "worker_safe": _as_bool(row["worker_safe"]),
                    "supervisor_notification_status": row["supervisor_notification_status"],
                },
            )
            conn.commit()
            snapshot = self._row_to_snapshot(self._get_row(conn, session_id))
            snapshot["status"] = "escalated"
            return snapshot
        finally:
            conn.close()

    # ── Helpers ────────────────────────────────────────────────────────────
    def _notification_payload(
        self,
        incident_id: str,
        session_id: str,
        severity: str,
        worker_safe: Optional[bool],
    ) -> Dict[str, Any]:
        return {
            "type": "incident.escalated",
            "incident_id": incident_id,
            "session_id": session_id,
            "severity": severity,
            "worker_safe": worker_safe,
            "source": "sentinel",
            "created_at": _utcnow(),
        }

    def _emit_transition_events(
        self,
        conn: sqlite3.Connection,
        incident_id: str,
        session_id: str,
        prev_status: Optional[str],
        new_status: str,
        immediate_actions: list,
    ) -> None:
        """Emit the audit events for a status transition (exactly once)."""
        source = "risk_engine"
        if new_status == "CRITICAL":
            self._append_audit(
                conn, incident_id, session_id, "critical_detected",
                source=source, details={"highest_severity": "CRITICAL"},
            )
            self._append_audit(
                conn, incident_id, session_id, "safety_instruction_given",
                source=source, details={"immediate_actions": immediate_actions},
            )
            self._append_audit(
                conn, incident_id, session_id, "safety_verification_started",
                source=source, details={"prompt": "Verify the worker is safely away from the equipment"},
            )
        elif new_status == "VERIFYING_SAFETY":
            self._append_audit(
                conn, incident_id, session_id, "safety_verification_started",
                source=source, details={"reason": "Worker has not confirmed they are safely away"},
            )
        # incident_escalated is emitted by escalate_incident() only.

    def get_snapshot(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = self._get_row(conn, session_id)
            if row is None:
                return None
            snapshot = self._row_to_snapshot(row)
            snapshot["status"] = "snapshot"
            return snapshot
        finally:
            conn.close()

    def list_audit_events(self, session_id: str) -> list[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT incident_id, event_type, source, details, created_at FROM audit_events "
                "WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [
                {
                    "incident_id": r["incident_id"],
                    "event_type": r["event_type"],
                    "source": r["source"],
                    "details": json.loads(r["details"]) if r["details"] else None,
                    "created_at": r["created_at"],
                }
                for r in rows
            ]
        finally:
            conn.close()


# ── Module-level singleton (isolated behind this service) ───────────────────
_service: Optional[IncidentService] = None


def get_incident_service() -> IncidentService:
    global _service
    if _service is None:
        _service = IncidentService()
    return _service


def reset_incident_service() -> None:
    """Test hook: drops the cached service so a fresh db_path takes effect."""
    global _service
    _service = None


def compose_snapshot_response(
    snapshot: Dict[str, Any],
    next_question_goal: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Merge an incident snapshot into a ToolResponse-compatible payload."""
    response = {k: snapshot.get(k) for k in _INCIDENT_FIELDS}
    response["incident_status"] = snapshot.get("incident_status")
    if next_question_goal:
        response["next_question_goal"] = next_question_goal
    response.update(extra)
    return response