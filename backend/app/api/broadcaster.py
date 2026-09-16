"""
SENTINEL Backend — Supervisor Real-Time Broadcast Manager (Phase 6)

Provides a decoupled event broadcaster for the Supervisor Command Center.
The RiskEngine and IncidentService remain independent and testable without WebSockets.
"""
import logging
from typing import Dict, Any, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class SupervisorConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Supervisor WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Supervisor WebSocket disconnected. Remaining connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self.active_connections:
            return
        
        dead_connections: List[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as exc:
                logger.warning(f"Failed to send to supervisor WebSocket: {exc}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


# Global singleton instance
connection_manager = SupervisorConnectionManager()


async def broadcast_incident_update(payload: Dict[str, Any]) -> None:
    """Broadcast an incident update event to all connected supervisor clients."""
    await connection_manager.broadcast(payload)
