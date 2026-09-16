"""
SENTINEL 2.0 Machine Information & Live Telemetry Service (Phase E)
"""
import logging
from typing import Optional, Union

from app.context.models import FactoryContext
from app.factory_data.models import (
    MachineInfo,
    MachineStatus,
    FactoryDataResult,
    DataCategory,
    DataFreshness,
)
from app.factory_data.provider import get_factory_data_provider, FactoryDataProvider

logger = logging.getLogger(__name__)


def resolve_target_machine(
    machine_id: Optional[str] = None,
    context: Optional[FactoryContext] = None,
) -> Optional[str]:
    """Resolves the effective machine ID using explicit query parameter or FactoryContext memory."""
    if machine_id and machine_id.strip():
        return machine_id.strip()
    if context and context.current_machine:
        return context.current_machine
    return None


def get_machine_info(
    machine_id: Optional[str] = None,
    context: Optional[FactoryContext] = None,
    provider: Optional[FactoryDataProvider] = None,
) -> FactoryDataResult:
    """Retrieves factual machine metadata (model, location, manufacturer, status)."""
    p = provider or get_factory_data_provider()
    target = resolve_target_machine(machine_id, context)

    if not target:
        return FactoryDataResult(
            found=False,
            data_type=DataCategory.HISTORICAL.value,
            message="Please specify which machine you are referring to.",
        )

    info: Optional[MachineInfo] = p.get_machine_info(target)
    if not info:
        return FactoryDataResult(
            found=False,
            machine_id=target,
            data_type=DataCategory.HISTORICAL.value,
            message=f"I don't have factory data for {target}.",
            machine_not_found=True,
        )

    msg = f"{info.name} is a {info.machine_type} ({info.model}) located in {info.location}."
    return FactoryDataResult(
        found=True,
        machine_id=info.machine_id,
        data_type=DataCategory.HISTORICAL.value,
        data=info,
        message=msg,
    )


def get_machine_status(
    machine_id: Optional[str] = None,
    context: Optional[FactoryContext] = None,
    provider: Optional[FactoryDataProvider] = None,
) -> FactoryDataResult:
    """Retrieves live/simulated telemetry status for a machine."""
    p = provider or get_factory_data_provider()
    target = resolve_target_machine(machine_id, context)

    if not target:
        return FactoryDataResult(
            found=False,
            data_type=DataCategory.LIVE.value,
            message="Please specify which machine you are referring to.",
        )

    status: Optional[MachineStatus] = p.get_machine_status(target)
    if not status:
        return FactoryDataResult(
            found=False,
            machine_id=target,
            data_type=DataCategory.LIVE.value,
            message=f"I don't have a current {target} status reading.",
            machine_not_found=True,
        )

    msg = format_machine_status_response(status)
    return FactoryDataResult(
        found=True,
        machine_id=status.machine_id,
        data_type=DataCategory.LIVE.value,
        data=status,
        message=msg,
        freshness=status.data_freshness,
    )


def format_machine_status_response(status: MachineStatus) -> str:
    """Formats machine telemetry into a concise voice response (1 sentence)."""
    source_label = "simulated as " if status.data_source == "SIMULATED" else ""
    return (
        f"{status.machine_id} is currently {source_label}{status.status.lower()} "
        f"at {status.temperature}°C with vibration at {status.vibration} mm/s."
    )
