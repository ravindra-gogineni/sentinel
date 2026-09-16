"""
Factory data provider services and data access utilities
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from app.factory_data.models import (
    MachineInfo,
    MachineStatus,
    MaintenanceRecord,
    WorkOrder,
    DataSource,
    DataFreshness,
)


class FactoryDataProvider(ABC):
    """Abstract Base Class for Factory Data Access (OPC-UA, MQTT, PLC, or Simulator)."""

    @abstractmethod
    def get_machine_info(self, machine_id: str) -> Optional[MachineInfo]:
        """Retrieves static machine metadata."""
        pass

    @abstractmethod
    def get_machine_status(self, machine_id: str) -> Optional[MachineStatus]:
        """Retrieves dynamic live/simulated telemetry status."""
        pass

    @abstractmethod
    def get_maintenance_history(self, machine_id: str) -> List[MaintenanceRecord]:
        """Retrieves historical maintenance records for a machine."""
        pass

    @abstractmethod
    def get_active_work_orders(self, machine_id: str) -> List[WorkOrder]:
        """Retrieves active work orders for a machine."""
        pass


class SimulatedFactoryDataProvider(FactoryDataProvider):
    """In-memory realistic factory data simulator for hackathon & test suite execution."""

    def __init__(self) -> None:
        self._machine_info: Dict[str, MachineInfo] = {
            "Machine 4": MachineInfo(
                machine_id="Machine 4",
                name="Machine 4 - High-Precision Milling Station",
                machine_type="Milling Station",
                location="Bay A, Line 2",
                manufacturer="PrecisionTech Industries",
                model="M4-Pro",
                installation_date="2024-03-15",
                operational_status="RUNNING",
            ),
            "Machine 7": MachineInfo(
                machine_id="Machine 7",
                name="Machine 7 - Automated Hydraulic Pressing Station",
                machine_type="Hydraulic Press",
                location="Bay C, Line 5",
                manufacturer="HydroDrive Systems",
                model="H7-Heavy",
                installation_date="2025-01-10",
                operational_status="RUNNING",
            ),
        }

        self._machine_status: Dict[str, MachineStatus] = {
            "Machine 4": MachineStatus(
                machine_id="Machine 4",
                status="RUNNING",
                temperature=68.4,
                vibration=2.7,
                pressure=4.2,
                runtime_hours=8214,
                power_state="ON",
                last_updated="2026-09-13T19:00:00Z",
                data_source=DataSource.SIMULATED.value,
                data_freshness=DataFreshness.CURRENT.value,
            ),
            "Machine 7": MachineStatus(
                machine_id="Machine 7",
                status="RUNNING",
                temperature=72.1,
                vibration=1.4,
                pressure=180.0,
                runtime_hours=3410,
                power_state="ON",
                last_updated="2026-09-13T19:00:00Z",
                data_source=DataSource.SIMULATED.value,
                data_freshness=DataFreshness.CURRENT.value,
            ),
        }

        self._maintenance_history: Dict[str, List[MaintenanceRecord]] = {
            "Machine 4": [
                MaintenanceRecord(
                    record_id="MNT-M4-2026-08",
                    machine_id="Machine 4",
                    service_type="Routine 500-Hour Inspection",
                    service_date="2026-08-28",
                    technician="Alex Rivera",
                    findings="Motor housing bearings inspected and lubricated. Drive belt tension within tolerance.",
                    actions="Lubricated bearings and re-torqued mounting bracket screws to 45 Nm.",
                    next_due_date="2026-11-28",
                ),
                MaintenanceRecord(
                    record_id="MNT-M4-2026-05",
                    machine_id="Machine 4",
                    service_type="Filter & Fluid Renewal",
                    service_date="2026-05-12",
                    technician="David Vance",
                    findings="Coolant fluid concentration slightly low.",
                    actions="Replaced coolant filter and flushed lines.",
                    next_due_date="2026-08-12",
                ),
            ],
            "Machine 7": [
                MaintenanceRecord(
                    record_id="MNT-M7-2026-07",
                    machine_id="Machine 7",
                    service_type="Hydraulic System Flush",
                    service_date="2026-07-15",
                    technician="Sarah Chen",
                    findings="Hydraulic fluid clear. Accumulator valve HDV-07 functioning normally.",
                    actions="Replaced hydraulic filter and topped off system fluid to 180 Bar operating pressure.",
                    next_due_date="2026-10-15",
                ),
            ],
        }

        self._work_orders: Dict[str, List[WorkOrder]] = {
            "Machine 4": [
                WorkOrder(
                    work_order_id="WO-M4-102",
                    machine_id="Machine 4",
                    title="Quarterly Motor Belt Replacement",
                    priority="MEDIUM",
                    status="IN_PROGRESS",
                    assigned_team="Maintenance Team Alpha",
                    created_at="2026-09-01",
                    due_date="2026-09-20",
                    description="Scheduled replacement of drive belt on motor housing assembly.",
                ),
            ],
            "Machine 7": [],  # No active work orders
        }

    def _normalize_machine_id(self, machine_id: str) -> str:
        if not machine_id:
            return ""
        m_trim = machine_id.strip()
        m_low = m_trim.lower()
        if "4" in m_low and "machine" in m_low:
            return "Machine 4"
        if "7" in m_low and "machine" in m_low:
            return "Machine 7"
        return m_trim

    def get_machine_info(self, machine_id: str) -> Optional[MachineInfo]:
        key = self._normalize_machine_id(machine_id)
        return self._machine_info.get(key)

    def get_machine_status(self, machine_id: str) -> Optional[MachineStatus]:
        key = self._normalize_machine_id(machine_id)
        return self._machine_status.get(key)

    def get_maintenance_history(self, machine_id: str) -> List[MaintenanceRecord]:
        key = self._normalize_machine_id(machine_id)
        return self._maintenance_history.get(key, [])

    def get_active_work_orders(self, machine_id: str) -> List[WorkOrder]:
        key = self._normalize_machine_id(machine_id)
        orders = self._work_orders.get(key, [])
        return [w for w in orders if w.status in ["OPEN", "IN_PROGRESS"]]


_provider: Optional[FactoryDataProvider] = None


def get_factory_data_provider() -> FactoryDataProvider:
    global _provider
    if _provider is None:
        _provider = SimulatedFactoryDataProvider()
    return _provider
