"""Invoice filing routes."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Query, BackgroundTasks

from ..auth import verify_token
from ..models import FileInvoiceResponse, Invoice, InvoiceListResponse, UpdateInvoiceStatusRequest
from ..sheets import get_sheets_service

router = APIRouter(tags=["invoices"])
logger = logging.getLogger(__name__)


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    q: Optional[str] = Query(None, description="Search by customer name or invoice number"),
    user: str = Depends(verify_token),
):
    """List all invoices, optionally filtered by search query."""
    svc = get_sheets_service()
    invoices_data = svc.get_all_invoices(search_query=q or "")

    invoices = [Invoice(**inv) for inv in invoices_data]
    return InvoiceListResponse(invoices=invoices, total=len(invoices))


def _add_watermark_background(invoice_number: str, drive_url: str):
    """Background task to add PAID watermark to PDF."""
    try:
        svc = get_sheets_service()
        svc.add_paid_watermark(drive_url)
        logger.info(f"Background watermark added for {invoice_number}")
    except Exception as e:
        logger.error(f"Background watermark failed for {invoice_number}: {e}")


@router.put("/invoices/{invoice_number}/status")
async def update_invoice_status(
    invoice_number: str,
    request: UpdateInvoiceStatusRequest,
    background_tasks: BackgroundTasks,
    user: str = Depends(verify_token),
):
    """Update the paid status of an invoice. If marking as paid, adds PAID watermark to PDF in background."""
    svc = get_sheets_service()
    result = svc.update_invoice_status(invoice_number, request.paid)

    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", f"Invoice {invoice_number} not found"))

    response = {
        "message": f"Invoice {invoice_number} marked as {'Paid' if request.paid else 'Unpaid'}",
        "paid": request.paid,
    }

    # Schedule watermark addition in background if marking as paid and has Drive URL
    if request.paid and result.get("drive_url"):
        background_tasks.add_task(_add_watermark_background, invoice_number, result["drive_url"])
        response["watermark_queued"] = True

    return response


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

    drive_error = result.get("drive_error", "")
    message = "Invoice filed successfully"
    if drive_error:
        message = f"Invoice logged but Drive upload failed: {drive_error}"

    return FileInvoiceResponse(
        message=message,
        drive_url=result.get("drive_url", ""),
        invoice_number=result.get("invoice_number", ""),
        drive_error=drive_error,
    )
