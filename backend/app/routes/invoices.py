"""Invoice filing routes."""

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException

from ..auth import verify_token
from ..models import FileInvoiceResponse
from ..sheets import get_sheets_service

router = APIRouter(tags=["invoices"])


@router.post("/invoices/file", response_model=FileInvoiceResponse)
async def file_invoice(
    invoice_data: str = Form(...),
    pdf: UploadFile = File(...),
    user: str = Depends(verify_token),
):
    """File an invoice: log to Google Sheets and upload PDF to Google Drive."""
    try:
        data = json.loads(invoice_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid invoice data JSON")

    customer_name = data.get("customer_name", "").strip()
    invoice_date = data.get("invoice_date", "")
    items = data.get("items", [])
    total = float(data.get("total", 0))
    paid = bool(data.get("paid", False))

    if not customer_name:
        raise HTTPException(status_code=400, detail="Customer name is required")
    if not items:
        raise HTTPException(status_code=400, detail="At least one item is required")

    # Build a compact items summary for the sheet cell
    items_summary = "; ".join(
        f"{it.get('product_name', '?')} x{it.get('qty', 0)}" for it in items
    )

    pdf_bytes = await pdf.read()

    svc = get_sheets_service()
    result = svc.file_invoice(
        customer_name=customer_name,
        invoice_date=invoice_date,
        items_summary=items_summary,
        total=total,
        paid=paid,
        pdf_bytes=pdf_bytes,
    )

    return FileInvoiceResponse(
        message="Invoice filed successfully",
        drive_url=result.get("drive_url", ""),
        invoice_number=result.get("invoice_number", ""),
    )
