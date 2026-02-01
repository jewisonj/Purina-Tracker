"""Pydantic models for request/response validation."""

from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    pin: str


class LoginResponse(BaseModel):
    token: str
    role: str
    expires_in_days: int = 7


class Product(BaseModel):
    row_number: int  # 1-indexed row in the sheet (for updates)
    material_no: str
    formula_code: str
    product_name: str
    product_form: str
    unit_weight: str
    purina_cost: float
    pallet_cost: float
    markup_pct: float
    retail_pre_tax: float
    retail_with_tax: float
    qty_on_hand: int
    reorder_point: int
    last_updated: str
    notes: str


class MarkupUpdate(BaseModel):
    markup_pct: float  # e.g. 0.25 for 25%


class ReorderUpdate(BaseModel):
    reorder_point: int


class InventoryAdjustment(BaseModel):
    material_no: str
    change_type: str  # "sale", "restock", "adjustment"
    quantity: int  # positive for add, negative for subtract
    notes: Optional[str] = ""


class BulkAdjustment(BaseModel):
    adjustments: list[InventoryAdjustment]


class LogEntry(BaseModel):
    timestamp: str
    product_name: str
    material_no: str
    change_type: str
    qty_changed: int
    previous_qty: int
    new_qty: int
    changed_by: str
    notes: str


class InvoiceItem(BaseModel):
    product_name: str
    material_no: str
    qty: int
    unit_price: float
    extended: float


class FileInvoiceRequest(BaseModel):
    customer_name: str
    invoice_date: str
    items: list[InvoiceItem]
    total: float
    paid: bool = False


class FileInvoiceResponse(BaseModel):
    message: str
    drive_url: str = ""
    invoice_number: str = ""
