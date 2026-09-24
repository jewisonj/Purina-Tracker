"""Price list import route."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from ..auth import verify_token
from ..sheets import calc_retail_pre_tax, calc_retail_with_tax, get_sheets_service

router = APIRouter(tags=["pricelist"])

# Categories we care about
WANTED_CATEGORIES = {"HORSE", "ALL PURPOSE"}


@router.get("/pricelist/archive")
async def get_archive(user: str = Depends(verify_token)):
    """Get the Price List Archive tab contents."""
    svc = get_sheets_service()
    ws = svc._get_worksheet("Price List Archive")
    data = ws.get_all_values()
    return {
        "headers": data[0] if data else [],
        "rows": data[1:] if len(data) > 1 else [],
    }


def _field(record: dict, *names: str) -> str:
    """Return the first non-empty value among column names.

    Purina has renamed CSV columns between exports (e.g. "Material No" ->
    "Material Number", "Single Unit List Price" -> "Single Unit Price"), so
    accept either spelling.
    """
    for name in names:
        value = record.get(name)
        if value:
            return value.strip()
    return ""


def _material_key(value: str) -> str:
    """Normalize a material number so "0046538" and "46538" match."""
    return value.strip().strip("'").lstrip("0")


def _price(value: str) -> float:
    try:
        return float(value.replace("$", "").replace(",", "")) if value else 0.0
    except ValueError:
        return 0.0


@router.post("/pricelist/import")
async def import_pricelist(
    file: UploadFile = File(...), user: str = Depends(verify_token)
):
    """Upload a new Purina CSV to refresh costs in the Inventory tab.

    Only Purina Cost (col F) and Pallet Cost (col G) change for existing
    products; markup and retail prices are left as they are.
    """
    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    csv_rows = list(csv.reader(io.StringIO(text)))
    if not csv_rows:
        raise HTTPException(status_code=400, detail="CSV is empty")
    headers = csv_rows[0]
    records = [dict(zip(headers, r)) for r in csv_rows[1:]]

    if not any(h in headers for h in ("Material No", "Material Number")):
        raise HTTPException(
            status_code=400,
            detail="CSV is missing a Material No / Material Number column",
        )

    svc = get_sheets_service()
    ws = svc._get_worksheet("Inventory")
    rows = ws.get_all_values()

    # Build lookup: material_no -> row_number
    material_to_row = {}
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0]:
            material_to_row[_material_key(row[0])] = i

    cost_updates = []
    new_rows = []
    new_products = []

    for record in records:
        category = record.get("Price List Category", "")
        product_name = _field(record, "Product Name", "Product Description")
        # Filter: only HORSE products + CA ALL STOCK
        is_horse = "HORSE" in category.upper()
        is_all_stock = "ALL PURPOSE" in category.upper() and "CA ALL STOCK" in product_name.upper()

        if not (is_horse or is_all_stock):
            continue

        material_no = _field(record, "Material No", "Material Number")
        if not material_no:
            continue

        single_price = _price(_field(record, "Single Unit List Price", "Single Unit Price"))
        pallet_price = _price(_field(record, "Full Pallet List Price", "Full Pallet Price"))

        key = _material_key(material_no)
        if key in material_to_row:
            # Update existing product costs (cols F:G)
            row_num = material_to_row[key]
            cost_updates.append({
                "range": f"F{row_num}:G{row_num}",
                "values": [[single_price, pallet_price]],
            })
        else:
            # New product - append
            formula_code = record.get("Formula Code", "")
            product_form = record.get("Product Form", "")
            unit_weight = _field(record, "Individual Unit Wt.", "Unit Weight")

            markup = 0.25
            pre_tax = calc_retail_pre_tax(single_price, markup)
            with_tax = calc_retail_with_tax(pre_tax)

            new_rows.append([
                material_no, formula_code, product_name, product_form, unit_weight,
                single_price, pallet_price, markup, pre_tax, with_tax,
                0, 5, "", ""  # qty=0, reorder=5, no timestamp, no notes
            ])
            new_products.append(product_name)

    # Batch writes to stay under the Sheets API per-minute write quota
    if cost_updates:
        ws.batch_update(cost_updates, value_input_option="USER_ENTERED")
    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    # Replace the Price List Archive with the full new CSV
    archive = svc._get_worksheet("Price List Archive")
    archive.clear()
    archive.update(range_name="A1", values=csv_rows, value_input_option="RAW")

    svc._invalidate_cache()

    updated = len(cost_updates)
    return {
        "updated": updated,
        "new_products": new_products,
        "message": f"Updated {updated} existing products, added {len(new_products)} new products.",
    }
