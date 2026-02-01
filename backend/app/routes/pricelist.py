"""Price list import route."""

import csv
import io

from fastapi import APIRouter, Depends, UploadFile, File

from ..auth import verify_token
from ..sheets import get_sheets_service

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


@router.post("/pricelist/import")
async def import_pricelist(
    file: UploadFile = File(...), user: str = Depends(verify_token)
):
    """Upload a new Purina CSV to refresh costs in the Inventory tab."""
    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    svc = get_sheets_service()
    ws = svc._get_worksheet("Inventory")
    rows = ws.get_all_values()

    # Build lookup: material_no -> row_number
    material_to_row = {}
    for i, row in enumerate(rows[1:], start=2):
        if row and row[0]:
            material_to_row[row[0]] = i

    updated = 0
    new_products = []

    for record in reader:
        category = record.get("Price List Category", "")
        # Filter: only HORSE products + CA ALL STOCK
        is_horse = "HORSE" in category.upper()
        is_all_stock = "ALL PURPOSE" in category.upper() and "CA ALL STOCK" in record.get("Product Name", "").upper()

        if not (is_horse or is_all_stock):
            continue

        material_no = record.get("Material No", "").strip()
        if not material_no:
            continue

        single_price = float(record.get("Single Unit List Price", 0) or 0)
        pallet_price = float(record.get("Full Pallet List Price", 0) or 0)

        if material_no in material_to_row:
            # Update existing product costs
            row_num = material_to_row[material_no]
            ws.update_cell(row_num, 6, single_price)   # Purina Cost (col F)
            ws.update_cell(row_num, 7, pallet_price)    # Pallet Cost (col G)
            updated += 1
        else:
            # New product - append
            formula_code = record.get("Formula Code", "")
            product_name = record.get("Product Name", "")
            product_form = record.get("Product Form", "")
            unit_weight = record.get("Individual Unit Wt.", "")

            from ..sheets import calc_retail_pre_tax, calc_retail_with_tax
            markup = 0.25
            pre_tax = calc_retail_pre_tax(single_price, markup)
            with_tax = calc_retail_with_tax(pre_tax)

            new_row = [
                material_no, formula_code, product_name, product_form, unit_weight,
                single_price, pallet_price, markup, pre_tax, with_tax,
                0, 5, "", ""  # qty=0, reorder=5, no timestamp, no notes
            ]
            ws.append_row(new_row, value_input_option="USER_ENTERED")
            new_products.append(product_name)

    svc._invalidate_cache()

    return {
        "updated": updated,
        "new_products": new_products,
        "message": f"Updated {updated} existing products, added {len(new_products)} new products.",
    }
