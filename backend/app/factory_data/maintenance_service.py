"""
SENTINEL 2.0 Maintenance History Service (Phase E)
"""
import logging
from typing import List, Optional

from app.context.models import FactoryContext
from app.factory_data.machine_service import resolve_target_machine
from app.factory_data.models import (
    MaintenanceRecord,
    FactoryDataResult,
    DataCategory,
)
from app.factory_data.provider import get_factory_data_provider, FactoryDataProvider

logger = logging.getLogger(__name__)


def get_maintenance_history(
    machine_id: Optional[str] = None,
    context: Optional[FactoryContext] = None,
    provider: Optional[FactoryDataProvider] = None,
) -> FactoryDataResult:
    """Retrieves historical maintenance records for a machine."""
    p = provider or get_factory_data_provider()
    target = resolve_target_machine(machine_id, context)

    if not target:
        return FactoryDataResult(
            found=False,
            data_type=DataCategory.HISTORICAL.value,
            message="Please specify which machine you are referring to.",
        )

    # Validate if machine exists first
    info = p.get_machine_info(target)
    if not info:
        return FactoryDataResult(
            found=False,
            machine_id=target,
            data_type=DataCategory.HISTORICAL.value,
            message=f"I don't have factory maintenance records for {target}.",
            machine_not_found=True,
        )

    records: List[MaintenanceRecord] = p.get_maintenance_history(target)
    if not records:
        return FactoryDataResult(
            found=True,
            machine_id=target,
            data_type=DataCategory.HISTORICAL.value,
            data=[],
            message=f"No maintenance records found for {target}.",
        )

    msg = format_maintenance_response(records)
    return FactoryDataResult(
        found=True,
        machine_id=target,
        data_type=DataCategory.HISTORICAL.value,
        data=records,
        message=msg,
    )


def format_maintenance_response(records: List[MaintenanceRecord]) -> str:
    """Formats maintenance records into a concise voice response (1–2 sentences)."""
    if not records:
        return "No maintenance records available."

    latest = records[0]
    return (
        f"{latest.machine_id} was last serviced on {latest.service_date} ({latest.service_type}). "
        f"{latest.findings}"
    )
