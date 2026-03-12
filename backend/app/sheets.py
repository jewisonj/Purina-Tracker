"""Google Sheets service with caching."""

import io
import json
import logging
import time
import math
from datetime import datetime, timezone
from typing import Optional

import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2.service_account import Credentials as SACredentials

# PDF manipulation imports
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import Color

from .config import get_settings
from .models import Product, LogEntry

logger = logging.getLogger(__name__)

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
TAB_INVOICES = "Invoices"

DRIVE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


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

    # ── Invoice filing ──────────────────────────────────────────────

    def _get_or_create_invoices_tab(self) -> gspread.Worksheet:
        """Get the Invoices tab, creating it with headers if it doesn't exist."""
        ss = self._get_spreadsheet()
        try:
            return ss.worksheet(TAB_INVOICES)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=TAB_INVOICES, rows=1000, cols=8)
            ws.append_row(
                ["Invoice #", "Date", "Customer", "Items Summary", "Total", "Paid", "Filed At", "Drive URL"],
                value_input_option="USER_ENTERED",
            )
            return ws

    def _next_invoice_number(self, ws: gspread.Worksheet) -> str:
        """Generate the next invoice number like INV-0001."""
        rows = ws.get_all_values()
        # rows[0] is header, data rows start at index 1
        count = len(rows) - 1 if len(rows) > 1 else 0
        return f"INV-{count + 1:04d}"

    def _build_drive_service(self):
        """Build a Google Drive API service using the same service account."""
        creds_json = self._settings.google_credentials_json
        if not creds_json:
            raise RuntimeError("GOOGLE_CREDENTIALS_JSON not set")
        creds_info = json.loads(creds_json)
        creds = SACredentials.from_service_account_info(creds_info, scopes=DRIVE_SCOPES)
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def upload_to_drive(self, file_bytes: bytes, filename: str, mime_type: str = "application/pdf") -> str:
        """Upload a file to a Shared Drive folder and return its web view URL."""
        folder_id = self._settings.google_drive_folder_id
        if not folder_id:
            raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID not set")

        logger.info("Uploading %s (%d bytes) to Drive folder %s", filename, len(file_bytes), folder_id)

        drive = self._build_drive_service()
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=False)

        uploaded = drive.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink, webContentLink",
            supportsAllDrives=True,
        ).execute()

        file_id = uploaded.get("id", "")
        drive_url = uploaded.get("webViewLink") or uploaded.get("webContentLink") or ""

        # Fallback: construct a direct link from the file ID
        if not drive_url and file_id:
            drive_url = f"https://drive.google.com/file/d/{file_id}/view"

        logger.info("Drive upload success: id=%s url=%s", file_id, drive_url)
        return drive_url

    def file_invoice(
        self,
        customer_name: str,
        invoice_date: str,
        items_summary: str,
        total: float,
        paid: bool,
        pdf_bytes: bytes | None = None,
    ) -> dict:
        """Log an invoice to the Invoices sheet and optionally upload PDF to Drive."""
        ws = self._get_or_create_invoices_tab()
        inv_num = self._next_invoice_number(ws)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        drive_url = ""
        drive_error = ""
        if not self._settings.google_drive_folder_id:
            drive_error = "GOOGLE_DRIVE_FOLDER_ID is not configured"
            logger.warning("GOOGLE_DRIVE_FOLDER_ID not set — skipping Drive upload")
        elif pdf_bytes:
            name_part = customer_name.strip().replace(" ", "_")[:20]
            date_part = invoice_date.replace("-", "")
            filename = f"Invoice_{name_part}_{date_part}.pdf"
            try:
                drive_url = self.upload_to_drive(pdf_bytes, filename)
            except Exception as exc:
                drive_error = str(exc)
                logger.error("Drive upload failed for %s: %s", inv_num, exc, exc_info=True)

        ws.append_row(
            [inv_num, invoice_date, customer_name, items_summary, f"${total:.2f}", "Yes" if paid else "No", now, drive_url],
            value_input_option="USER_ENTERED",
        )

        return {"invoice_number": inv_num, "drive_url": drive_url, "drive_error": drive_error}

    def get_all_invoices(self, search_query: str = "") -> list[dict]:
        """Get all invoices from the Invoices sheet."""
        try:
            ws = self._get_or_create_invoices_tab()
        except gspread.WorksheetNotFound:
            return []

        rows = ws.get_all_values()
        if len(rows) <= 1:  # Only header or empty
            return []

        # Header: Invoice #, Date, Customer, Items Summary, Total, Paid, Filed At, Drive URL
        invoices = []
        for row in rows[1:]:  # Skip header
            if len(row) < 8:
                continue  # Skip malformed rows

            invoice = {
                "invoice_number": row[0],
                "date": row[1],
                "customer": row[2],
                "items_summary": row[3],
                "total": row[4],
                "paid": row[5].lower() in ("yes", "true", "1"),
                "filed_at": row[6],
                "drive_url": row[7] if len(row) > 7 else "",
            }

            # Apply search filter if provided
            if search_query:
                query_lower = search_query.lower()
                if (query_lower not in invoice["customer"].lower() and
                    query_lower not in invoice["invoice_number"].lower()):
                    continue

            invoices.append(invoice)

        # Return most recent first
        invoices.reverse()
        return invoices

    def update_invoice_status(self, invoice_number: str, paid: bool) -> dict:
        """Update the paid status of an invoice. Returns result dict with drive_url for background watermarking."""
        result = {"success": False, "drive_url": "", "error": ""}

        try:
            ws = self._get_or_create_invoices_tab()
        except gspread.WorksheetNotFound:
            result["error"] = "Invoices tab not found"
            return result

        rows = ws.get_all_values()
        if len(rows) <= 1:
            result["error"] = "No invoices found"
            return result

        # Find the invoice row (column A = Invoice #)
        for idx, row in enumerate(rows[1:], start=2):  # Start at row 2 (1-indexed)
            if len(row) > 0 and row[0] == invoice_number:
                # Update column F (Paid) - column 6
                ws.update_cell(idx, 6, "Yes" if paid else "No")
                result["success"] = True

                # Return drive_url so caller can queue watermark in background
                if len(row) > 7 and row[7]:
                    result["drive_url"] = row[7]

                return result

        result["error"] = f"Invoice {invoice_number} not found"
        return result

    def add_paid_watermark(self, drive_url: str) -> None:
        """Public method to add PAID watermark to a PDF in Google Drive."""
        self._add_paid_watermark_to_drive_pdf(drive_url)

    def _create_paid_watermark(self, width: float, height: float) -> io.BytesIO:
        """Create a PAID watermark PDF page."""
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(width, height))

        # Semi-transparent red color for PAID stamp
        c.setFillColor(Color(0.77, 0.07, 0.19, alpha=0.3))  # Purina red with transparency

        # Rotate and position the watermark diagonally
        c.saveState()
        c.translate(width / 2, height / 2)
        c.rotate(45)

        # Draw PAID text
        c.setFont("Helvetica-Bold", 72)
        c.drawCentredString(0, 0, "PAID")

        c.restoreState()
        c.save()

        packet.seek(0)
        return packet

    def _extract_file_id_from_url(self, drive_url: str) -> str:
        """Extract Google Drive file ID from URL."""
        # Handle various Google Drive URL formats
        # https://drive.google.com/file/d/FILE_ID/view
        # https://drive.google.com/open?id=FILE_ID
        if "/d/" in drive_url:
            parts = drive_url.split("/d/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        elif "id=" in drive_url:
            return drive_url.split("id=")[1].split("&")[0]
        return ""

    def _add_paid_watermark_to_drive_pdf(self, drive_url: str) -> None:
        """Download PDF from Drive, add PAID watermark, and re-upload."""
        file_id = self._extract_file_id_from_url(drive_url)
        if not file_id:
            raise ValueError(f"Could not extract file ID from URL: {drive_url}")

        drive = self._build_drive_service()

        # Download the PDF
        request = drive.files().get_media(fileId=file_id)
        pdf_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(pdf_buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        pdf_buffer.seek(0)

        # Read the PDF and add watermark to each page
        reader = PdfReader(pdf_buffer)
        writer = PdfWriter()

        for page in reader.pages:
            # Get page dimensions
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            # Create watermark for this page size
            watermark_buffer = self._create_paid_watermark(width, height)
            watermark_reader = PdfReader(watermark_buffer)
            watermark_page = watermark_reader.pages[0]

            # Merge watermark onto original page
            page.merge_page(watermark_page)
            writer.add_page(page)

        # Write the watermarked PDF to buffer
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)

        # Re-upload to Drive (update existing file)
        media = MediaIoBaseUpload(output_buffer, mimetype="application/pdf", resumable=False)
        drive.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True,
        ).execute()

        logger.info(f"Added PAID watermark to PDF: {file_id}")


# Singleton instance
_sheets_service: Optional[SheetsService] = None


def get_sheets_service() -> SheetsService:
    global _sheets_service
    if _sheets_service is None:
        _sheets_service = SheetsService()
    return _sheets_service
