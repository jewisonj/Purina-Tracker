"""Google Sheets service with caching."""

import json
import time
import math
from datetime import datetime, timezone
from typing import Optional

import gspread

from .config import get_settings
from .models import Product, LogEntry

# Column indices (0-based) in the Inventory tab
COL = {
    "material_no": 0,
    "formula_code": 1,
    "product_name": 2,
    "product_form": 3,
    "unit_weight": 4,
    "purina_cost": 5,
    "pallet_cost": 6,
    "markup_pct": 7,
    "retail_pre_tax": 8,
    "retail_with_tax": 9,
    "qty_on_hand": 10,
    "reorder_point": 11,
    "last_updated": 12,
    "notes": 13,
}

TAB_INVENTORY = "Inventory"
TAB_LOG = "Inventory Log"
TAB_ARCHIVE = "Price List Archive"


def ceil_quarter(value: float) -> float:
    """Round up to the nearest $0.25."""
    return math.ceil(value * 4) / 4


def calc_retail_pre_tax(cost: float, markup_pct: float) -> float:
    return ceil_quarter(cost * (1 + markup_pct))


def calc_retail_with_tax(pre_tax: float, tax_rate: float = 0.055) -> float:
    return ceil_quarter(pre_tax * (1 + tax_rate))


class SheetsService:
    """Google Sheets client with in-memory caching."""

    def __init__(self):
        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._cache: dict = {}
        self._cache_time: float = 0
        self._settings = get_settings()

    def _get_client(self) -> gspread.Client:
        if self._client is None:
            creds_json = self._settings.google_credentials_json
            if not creds_json:
                raise RuntimeError("GOOGLE_CREDENTIALS_JSON not set")
            creds = json.loads(creds_json)
            self._client = gspread.service_account_from_dict(creds)
        return self._client

    def _get_spreadsheet(self) -> gspread.Spreadsheet:
        if self._spreadsheet is None:
            client = self._get_client()
            sheet_id = self._settings.google_sheet_id
            if not sheet_id:
                raise RuntimeError("GOOGLE_SHEET_ID not set")
            self._spreadsheet = client.open_by_key(sheet_id)
        return self._spreadsheet

    def _get_worksheet(self, tab_name: str) -> gspread.Worksheet:
        return self._get_spreadsheet().worksheet(tab_name)

    def _invalidate_cache(self):
        self._cache = {}
        self._cache_time = 0

    def _is_cache_valid(self) -> bool:
        return (
            bool(self._cache)
            and (time.time() - self._cache_time) < self._settings.cache_ttl_seconds
        )

    def get_all_products(self) -> list[Product]:
        """Get all products from the Inventory tab."""
        if self._is_cache_valid() and "products" in self._cache:
            return self._cache["products"]

        ws = self._get_worksheet(TAB_INVENTORY)
        rows = ws.get_all_values()

        products = []
        for i, row in enumerate(rows[1:], start=2):  # skip header, row_number is 1-indexed
            if not row or not row[0]:
                continue
            try:
                purina_cost = float(row[COL["purina_cost"]] or 0)
                pallet_cost = float(row[COL["pallet_cost"]] or 0)
                markup_pct = float(row[COL["markup_pct"]] or 0.25)
                pre_tax = float(row[COL["retail_pre_tax"]] or 0)
                with_tax = float(row[COL["retail_with_tax"]] or 0)
                qty = int(float(row[COL["qty_on_hand"]] or 0))
                reorder = int(float(row[COL["reorder_point"]] or 5))
            except (ValueError, IndexError):
                continue

            products.append(Product(
                row_number=i,
                material_no=row[COL["material_no"]],
                formula_code=row[COL["formula_code"]],
                product_name=row[COL["product_name"]],
                product_form=row[COL["product_form"]],
                unit_weight=row[COL["unit_weight"]],
                purina_cost=purina_cost,
                pallet_cost=pallet_cost,
                markup_pct=markup_pct,
                retail_pre_tax=pre_tax if pre_tax else calc_retail_pre_tax(purina_cost, markup_pct),
                retail_with_tax=with_tax if with_tax else calc_retail_with_tax(
                    pre_tax if pre_tax else calc_retail_pre_tax(purina_cost, markup_pct)
                ),
                qty_on_hand=qty,
                reorder_point=reorder,
                last_updated=row[COL["last_updated"]] if len(row) > COL["last_updated"] else "",
                notes=row[COL["notes"]] if len(row) > COL["notes"] else "",
            ))

        self._cache["products"] = products
        self._cache_time = time.time()
        return products

    def _find_product_row(self, material_no: str) -> tuple[int, list[str]]:
        """Find the row number and data for a product by material number."""
        ws = self._get_worksheet(TAB_INVENTORY)
        rows = ws.get_all_values()
        for i, row in enumerate(rows[1:], start=2):
            if row and row[COL["material_no"]] == material_no:
                return i, row
        raise ValueError(f"Product not found: {material_no}")

    def update_markup(self, material_no: str, markup_pct: float) -> Product:
        """Update markup % for a product. Recalculates retail prices."""
        row_num, row = self._find_product_row(material_no)
        ws = self._get_worksheet(TAB_INVENTORY)

        purina_cost = float(row[COL["purina_cost"]] or 0)
        pre_tax = calc_retail_pre_tax(purina_cost, markup_pct)
        with_tax = calc_retail_with_tax(pre_tax)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        # Update markup, pre-tax, with-tax, last_updated (H, I, J, M columns = 8, 9, 10, 13 in 1-indexed)
        ws.update_cell(row_num, COL["markup_pct"] + 1, markup_pct)
        ws.update_cell(row_num, COL["retail_pre_tax"] + 1, pre_tax)
        ws.update_cell(row_num, COL["retail_with_tax"] + 1, with_tax)
        ws.update_cell(row_num, COL["last_updated"] + 1, now)

        self._invalidate_cache()

        # Return updated product
        products = self.get_all_products()
        return next(p for p in products if p.material_no == material_no)

    def update_reorder_point(self, material_no: str, reorder_point: int) -> Product:
        """Update reorder point for a product."""
        row_num, _ = self._find_product_row(material_no)
        ws = self._get_worksheet(TAB_INVENTORY)

        ws.update_cell(row_num, COL["reorder_point"] + 1, reorder_point)
        ws.update_cell(row_num, COL["last_updated"] + 1,
                       datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))

        self._invalidate_cache()
        products = self.get_all_products()
        return next(p for p in products if p.material_no == material_no)

    def adjust_inventory(
        self, material_no: str, change_type: str, quantity: int, notes: str = "", changed_by: str = "web"
    ) -> Product:
        """Adjust inventory for a single product and log the change."""
        row_num, row = self._find_product_row(material_no)
        ws = self._get_worksheet(TAB_INVENTORY)

        previous_qty = int(float(row[COL["qty_on_hand"]] or 0))
        new_qty = previous_qty + quantity
        if new_qty < 0:
            new_qty = 0
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        # Update qty and timestamp
        ws.update_cell(row_num, COL["qty_on_hand"] + 1, new_qty)
        ws.update_cell(row_num, COL["last_updated"] + 1, now)

        # Append to log
        self._append_log(
            product_name=row[COL["product_name"]],
            material_no=material_no,
            change_type=change_type,
            qty_changed=quantity,
            previous_qty=previous_qty,
            new_qty=new_qty,
            changed_by=changed_by,
            notes=notes,
        )

        self._invalidate_cache()
        products = self.get_all_products()
        return next(p for p in products if p.material_no == material_no)

    def bulk_adjust_inventory(
        self, adjustments: list[dict], changed_by: str = "web"
    ) -> list[Product]:
        """Adjust inventory for multiple products."""
        results = []
        for adj in adjustments:
            product = self.adjust_inventory(
                material_no=adj["material_no"],
                change_type=adj["change_type"],
                quantity=adj["quantity"],
                notes=adj.get("notes", ""),
                changed_by=changed_by,
            )
            results.append(product)
        return results

    def _append_log(
        self,
        product_name: str,
        material_no: str,
        change_type: str,
        qty_changed: int,
        previous_qty: int,
        new_qty: int,
        changed_by: str,
        notes: str,
    ):
        """Append a row to the Inventory Log tab."""
        ws = self._get_worksheet(TAB_LOG)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row(
            [now, product_name, material_no, change_type, qty_changed, previous_qty, new_qty, changed_by, notes],
            value_input_option="USER_ENTERED",
        )

    def get_log(self, limit: int = 100) -> list[LogEntry]:
        """Get recent log entries."""
        ws = self._get_worksheet(TAB_LOG)
        rows = ws.get_all_values()

        entries = []
        for row in rows[1:]:  # skip header
            if not row or not row[0]:
                continue
            try:
                entries.append(LogEntry(
                    timestamp=row[0],
                    product_name=row[1],
                    material_no=row[2],
                    change_type=row[3],
                    qty_changed=int(float(row[4] or 0)),
                    previous_qty=int(float(row[5] or 0)),
                    new_qty=int(float(row[6] or 0)),
                    changed_by=row[7] if len(row) > 7 else "",
                    notes=row[8] if len(row) > 8 else "",
                ))
            except (ValueError, IndexError):
                continue

        # Return most recent first, limited
        entries.reverse()
        return entries[:limit]

    def get_low_stock(self) -> list[Product]:
        """Get products at or below reorder point."""
        products = self.get_all_products()
        return [p for p in products if p.qty_on_hand <= p.reorder_point]


# Singleton instance
_sheets_service: Optional[SheetsService] = None


def get_sheets_service() -> SheetsService:
    global _sheets_service
    if _sheets_service is None:
        _sheets_service = SheetsService()
    return _sheets_service
