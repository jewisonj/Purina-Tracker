"""Inventory routes."""

from fastapi import APIRouter, Depends, Query

from ..auth import verify_token
from ..models import InventoryAdjustment, BulkAdjustment, Product, LogEntry
from ..sheets import get_sheets_service

router = APIRouter(tags=["inventory"])


@router.post("/inventory/adjust", response_model=Product)
async def adjust_inventory(
    body: InventoryAdjustment, user: str = Depends(verify_token)
):
    svc = get_sheets_service()
    return svc.adjust_inventory(
        material_no=body.material_no,
        change_type=body.change_type,
        quantity=body.quantity,
        notes=body.notes or "",
        changed_by="web",
    )


@router.post("/inventory/bulk-adjust", response_model=list[Product])
async def bulk_adjust(body: BulkAdjustment, user: str = Depends(verify_token)):
    svc = get_sheets_service()
    adjustments = [adj.model_dump() for adj in body.adjustments]
    return svc.bulk_adjust_inventory(adjustments, changed_by="web")


@router.get("/inventory/log", response_model=list[LogEntry])
async def get_log(
    limit: int = Query(default=100, le=500),
    user: str = Depends(verify_token),
):
    svc = get_sheets_service()
    return svc.get_log(limit=limit)


@router.get("/inventory/low-stock", response_model=list[Product])
async def get_low_stock(user: str = Depends(verify_token)):
    svc = get_sheets_service()
    return svc.get_low_stock()
