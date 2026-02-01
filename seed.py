"""
Seed script: Populate the Google Sheet Inventory tab from the Purina CSV.

Usage:
  1. Set up your .env file with GOOGLE_CREDENTIALS_JSON and GOOGLE_SHEET_ID
  2. pip install gspread python-dotenv
  3. python seed.py

This will:
  - Create/clear the Inventory, Inventory Log, and Price List Archive tabs
  - Import HORSE products + CA ALL STOCK from the Purina CSV
  - Set default 25% markup and reorder point of 5
  - Add formulas for retail price columns
"""

import csv
import json
import os
import sys
import math
from pathlib import Path

from dotenv import load_dotenv
import gspread

load_dotenv()

# Config
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1fTIf-pbn0zeihe6PSGaeD_EhSOo3S7JMJK-OxYkLrjE")
CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
CSV_PATH = Path(__file__).parent / "PriceList_2026-01-31T13_33_28.csv"
DEFAULT_MARKUP = 0.25
DEFAULT_REORDER = 5


def ceil_quarter(value):
    return math.ceil(value * 4) / 4


def connect():
    if not CREDS_JSON:
        # Try loading from file
        creds_file = Path(__file__).parent / "service-account.json"
        if creds_file.exists():
            return gspread.service_account(filename=str(creds_file))
        print("ERROR: Set GOOGLE_CREDENTIALS_JSON in .env or place service-account.json in project root")
        sys.exit(1)
    creds = json.loads(CREDS_JSON)
    return gspread.service_account_from_dict(creds)


def get_or_create_worksheet(spreadsheet, title, rows=1000, cols=20):
    """Get existing worksheet or create a new one."""
    try:
        ws = spreadsheet.worksheet(title)
        ws.clear()
        return ws
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


def load_csv():
    """Load and filter the Purina CSV for relevant products."""
    products = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            category = row.get("Price List Category", "")
            product_name = row.get("Product Name", "")

            # Keep all HORSE products + CA ALL STOCK from ALL PURPOSE
            is_horse = category.strip().upper() == "HORSE"
            is_ca_allstock = (
                "ALL PURPOSE" in category.upper()
                and "CA ALL STOCK" in product_name.upper()
            )

            if not (is_horse or is_ca_allstock):
                continue

            single_price = float(row.get("Single Unit List Price", 0) or 0)
            pallet_price = float(row.get("Full Pallet List Price", 0) or 0)

            products.append({
                "material_no": row.get("Material No", "").strip(),
                "formula_code": row.get("Formula Code", "").strip(),
                "product_name": product_name.strip(),
                "product_form": row.get("Product Form", "").strip(),
                "unit_weight": row.get("Individual Unit Wt.", "").strip(),
                "purina_cost": single_price,
                "pallet_cost": pallet_price,
            })

    # Sort alphabetically by product name
    products.sort(key=lambda p: p["product_name"])
    return products


def seed_inventory(spreadsheet, products):
    """Create and populate the Inventory tab."""
    ws = get_or_create_worksheet(spreadsheet, "Inventory")

    # Header row
    headers = [
        "Material No", "Formula Code", "Product Name", "Product Form",
        "Unit Weight", "Purina Cost", "Pallet Cost", "Markup %",
        "Retail Pre-Tax", "Retail w/ Tax", "Qty On Hand",
        "Reorder Point", "Last Updated", "Notes"
    ]

    rows = [headers]
    for p in products:
        cost = p["purina_cost"]
        pre_tax = ceil_quarter(cost * (1 + DEFAULT_MARKUP))
        with_tax = ceil_quarter(pre_tax * 1.055)

        rows.append([
            p["material_no"],
            p["formula_code"],
            p["product_name"],
            p["product_form"],
            p["unit_weight"],
            cost,
            p["pallet_cost"],
            DEFAULT_MARKUP,
            pre_tax,
            with_tax,
            0,  # Qty on hand - to be set during first physical count
            DEFAULT_REORDER,
            "",  # Last Updated
            "",  # Notes
        ])

    ws.update(range_name="A1", values=rows, value_input_option="USER_ENTERED")

    # Format header row bold
    ws.format("A1:N1", {"textFormat": {"bold": True}})

    print(f"  Inventory tab: {len(products)} products")
    return ws


def seed_log(spreadsheet):
    """Create the Inventory Log tab with headers."""
    ws = get_or_create_worksheet(spreadsheet, "Inventory Log")
    headers = [
        "Timestamp", "Product Name", "Material No", "Change Type",
        "Qty Changed", "Previous Qty", "New Qty", "Changed By", "Notes"
    ]
    ws.update(range_name="A1", values=[headers], value_input_option="USER_ENTERED")
    ws.format("A1:I1", {"textFormat": {"bold": True}})
    print("  Inventory Log tab: headers created")


def seed_archive(spreadsheet):
    """Dump the full CSV into the Price List Archive tab."""
    ws = get_or_create_worksheet(spreadsheet, "Price List Archive")

    rows = []
    with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    # gspread has a limit on batch updates, write in chunks
    chunk_size = 200
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        start_row = i + 1
        ws.update(range_name=f"A{start_row}", values=chunk, value_input_option="USER_ENTERED")

    ws.format("A1:R1", {"textFormat": {"bold": True}})
    print(f"  Price List Archive tab: {len(rows) - 1} rows")


def main():
    print("Connecting to Google Sheets...")
    gc = connect()
    spreadsheet = gc.open_by_key(SHEET_ID)
    print(f"  Sheet: {spreadsheet.title}")

    print("\nLoading Purina CSV...")
    products = load_csv()
    print(f"  Found {len(products)} products (HORSE + CA ALL STOCK)")

    print("\nSeeding tabs...")
    seed_inventory(spreadsheet, products)
    seed_log(spreadsheet)
    seed_archive(spreadsheet)

    print("\nDone! Your Google Sheet is ready.")
    print(f"  https://docs.google.com/spreadsheets/d/{SHEET_ID}")
    print("\nNext steps:")
    print("  1. Open the sheet and verify the data looks correct")
    print("  2. Do your first physical inventory count via the web app")
    print("  3. Adjust markup % for any products that need different pricing")


if __name__ == "__main__":
    main()
