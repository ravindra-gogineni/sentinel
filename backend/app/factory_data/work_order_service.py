"""
SENTINEL 2.0 Active Work Orders Service (Phase E)
"""
import logging
from typing import List, Optional

from app.context.models import FactoryContext
from app.factory_data.machine_service import resolve_target_machine
from app.factory_data.models import (
    WorkOrder,
    FactoryDataResult,
    DataCategory,
)
from app.factory_data.provider import get_factory_data_provider, FactoryDataProvider

logger = logging.getLogger(__name__)


def get_active_work_orders(
    machine_id: Optional[str] = None,
    context: Optional[FactoryContext] = None,
    provider: Optional[FactoryDataProvider] = None,
) -> FactoryDataResult:
    """Retrieves active work orders for a machine."""
    p = provider or get_factory_data_provider()
    target = resolve_target_machine(machine_id, context)

    if not target:
        return FactoryDataResult(
            found=False,
            data_type=DataCategory.HISTORICAL.value,
            message="Please specify which machine you are referring to.",
        )

    # Validate machine existence
    info = p.get_machine_info(target)
    if not info:
        return FactoryDataResult(
            found=False,
            machine_id=target,
            data_type=DataCategory.HISTORICAL.value,
            message=f"I don't have work order records for {target}.",
            machine_not_found=True,
        )

    orders: List[WorkOrder] = p.get_active_work_orders(target)
    msg = format_work_orders_response(orders, target)

    return FactoryDataResult(
        found=True,
        machine_id=target,
        data_type=DataCategory.HISTORICAL.value,
        data=orders,
        message=msg,
    )


def format_work_orders_response(orders: List[WorkOrder], machine_id: str) -> str:
    """Formats active work orders into a concise voice response (1 sentence)."""
    if not orders:
        return f"There are no active work orders for {machine_id}."

    if len(orders) == 1:
        wo = orders[0]
        return f"{machine_id} has 1 active work order ({wo.work_order_id}): {wo.title}."

    titles = ", ".join([w.title for w in orders])
    return f"{machine_id} has {len(orders)} active work orders: {titles}."
