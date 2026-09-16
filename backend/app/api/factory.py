"""
SENTINEL Backend — Factory Data REST API Router (Phase E)

Strictly READ-ONLY REST endpoints for retrieving factory metadata,
live/simulated telemetry status, maintenance records, and active work orders.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from app.factory_data import (
    get_machine_info,
    get_machine_status,
    get_maintenance_history,
    get_active_work_orders,
)

router = APIRouter(prefix="/api/factory", tags=["factory"])


@router.get("/machines/{machine_id}", response_model=Dict[str, Any])
async def get_machine_info_endpoint(machine_id: str) -> Dict[str, Any]:
    """Retrieves metadata info for a specific machine."""
    res = get_machine_info(machine_id=machine_id)
    if not res.found:
        raise HTTPException(status_code=404, detail=res.message)
    return res.model_dump()


@router.get("/machines/{machine_id}/status", response_model=Dict[str, Any])
async def get_machine_status_endpoint(machine_id: str) -> Dict[str, Any]:
    """Retrieves live/simulated telemetry status for a specific machine."""
    res = get_machine_status(machine_id=machine_id)
    if not res.found:
        raise HTTPException(status_code=404, detail=res.message)
    return res.model_dump()


@router.get("/machines/{machine_id}/maintenance", response_model=Dict[str, Any])
async def get_machine_maintenance_endpoint(machine_id: str) -> Dict[str, Any]:
    """Retrieves maintenance history records for a specific machine."""
    res = get_maintenance_history(machine_id=machine_id)
    if not res.found:
        raise HTTPException(status_code=404, detail=res.message)
    return res.model_dump()


@router.get("/machines/{machine_id}/work-orders", response_model=Dict[str, Any])
async def get_machine_work_orders_endpoint(machine_id: str) -> Dict[str, Any]:
    """Retrieves active work orders for a specific machine."""
    res = get_active_work_orders(machine_id=machine_id)
    if not res.found:
        raise HTTPException(status_code=404, detail=res.message)
    return res.model_dump()
