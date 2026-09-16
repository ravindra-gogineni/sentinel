"""
SENTINEL 2.0 Factory Data Models (Phase E)
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DataCategory(str, Enum):
    LIVE = "LIVE"
    HISTORICAL = "HISTORICAL"
    STATIC_DOCUMENT = "STATIC_DOCUMENT"


class DataFreshness(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class DataSource(str, Enum):
    SIMULATED = "SIMULATED"
    LIVE_SENSOR = "LIVE_SENSOR"
    HISTORICAL_DB = "HISTORICAL_DB"


class MachineInfo(BaseModel):
    """Factual static/operational metadata for a machine."""
    machine_id: str
    name: str
    machine_type: str
    location: str
    manufacturer: str
    model: str
    installation_date: str
    operational_status: str


class MachineStatus(BaseModel):
    """Dynamic live/simulated telemetry status for a machine."""
    machine_id: str
    status: str  # e.g., "RUNNING", "IDLE", "MAINTENANCE"
    temperature: float  # °C
    vibration: float    # mm/s
    pressure: float     # Bar / PSI
    runtime_hours: int
    power_state: str    # "ON", "OFF", "STANDBY"
    last_updated: str
    data_source: str = DataSource.SIMULATED.value
    data_freshness: str = DataFreshness.CURRENT.value


class MaintenanceRecord(BaseModel):
    """Structured historical record of machine maintenance."""
    record_id: str
    machine_id: str
    service_type: str
    service_date: str
    technician: str
    findings: str
    actions: str
    next_due_date: str


class WorkOrder(BaseModel):
    """Structured record of an active or historical work order."""
    work_order_id: str
    machine_id: str
    title: str
    priority: str
    status: str
    assigned_team: str
    created_at: str
    due_date: str
    description: str


class FactoryDataResult(BaseModel):
    """Container for factory data query responses with source provenance."""
    found: bool
    machine_id: Optional[str] = None
    data_type: str  # LIVE, HISTORICAL
    source: str = "FACTORY_DATA"
    data: Optional[Any] = None
    message: str
    freshness: str = DataFreshness.CURRENT.value
    machine_not_found: bool = False
