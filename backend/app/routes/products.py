"""Product routes."""

from fastapi import APIRouter, Depends

from ..auth import verify_token
from ..models import Product, MarkupUpdate, ReorderUpdate
from ..sheets import get_sheets_service

router = APIRouter(tags=["products"])


@router.get("/products", response_model=list[Product])
async def list_products(user: str = Depends(verify_token)):
    svc = get_sheets_service()
    return svc.get_all_products()


@router.put("/products/{material_no}/markup", response_model=Product)
async def update_markup(
    material_no: str, body: MarkupUpdate, user: str = Depends(verify_token)
):
    svc = get_sheets_service()
    return svc.update_markup(material_no, body.markup_pct)


@router.put("/products/{material_no}/reorder", response_model=Product)
async def update_reorder(
    material_no: str, body: ReorderUpdate, user: str = Depends(verify_token)
):
    svc = get_sheets_service()
    return svc.update_reorder_point(material_no, body.reorder_point)
