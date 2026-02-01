"""Add individual-unit products from case packs + Mare's Match products."""

import json
import os

from dotenv import load_dotenv
import gspread

load_dotenv("J:/Purina-Tracker/backend/.env")

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

# New rows to add: products sold individually from case packs, plus Mare's Match
# [Material No, Formula Code, Product Name, Form, Weight, Cost, Pallet Cost, Markup%, PreTax, w/Tax, Qty, Reorder, Updated, Notes]
NEW_PRODUCTS = [
    # Omega Match Ahiflower Oil - sold per 32oz bottle from 8x32oz case ($213.08/8 = $26.64)
    ["3005953-946-EA", "", "OMEGA MATCH AHIFLOWER OIL 32OZ", "Liquid", "32OZ",
     26.64, 0, 0.3996, 37.29, 39.34, 1, 2, "", "Per bottle from 8x32oz case"],

    # Systemiq Probiotic - sold per 2LB unit from 6x2LB case ($225.33/6 = $37.56)
    ["3009564-246-EA", "", "EQUINE SYSTEMIQ PROBIOTIC 2LB", "Powder", "2LB",
     37.56, 0, 0.5997, 60.09, 63.39, 1, 2, "", "Per unit from 6x2LB case"],

    # RepleniMash 7LB - sold per bag from 4x7LB case ($39.93/4 = $9.98)
    ["3006758-146-EA", "", "REPLENIMASH 7LB", "Pellets", "7LB",
     9.98, 0, 0.2876, 12.85, 13.56, 1, 2, "", "Per bag from 4x7LB case"],

    # Apple & Oat Horse Treats - sold per 3.5LB bag from 6-pack ($26.85/6 = $4.48)
    ["3003259-746-EA", "", "PUR HORSE TREATS APPLE+OAT 3.5LB", "Treats", "3.5LB",
     4.48, 0, 0.3772, 6.17, 6.51, 1, 2, "", "Per bag from 6x3.5LB pack"],

    # Nicker Makers Horse Treats - sold per 3.5LB bag from 6-pack ($26.85/6 = $4.48)
    ["3003256-746-EA", "", "PUR NICKER MAKERS TREATS 3.5LB", "Treats", "3.5LB",
     4.48, 0, 0.3772, 6.17, 6.51, 1, 2, "", "Per bag from 6x3.5LB pack"],

    # Outlast Horse Treats - sold per 3.5LB bag from 6-pack ($34.14/6 = $5.69)
    ["3005457-746-EA", "", "PUR OUTLAST HORSE TREATS 3.5LB", "Treats", "3.5LB",
     5.69, 0, 0.3831, 7.87, 8.30, 1, 2, "", "Per bag from 6x3.5LB pack"],

    # Mare's Match Foal Milk Replacer - different supplier, cost TBD
    ["MARES-MATCH-MLK", "", "MARE'S MATCH FOAL MILK REPLACER", "Powder", "25LB",
     0, 0, 0, 75.84, 80.01, 1, 2, "", "Non-Purina product - enter cost when known"],

    # Mare's Match Transition Pellets - different supplier, cost TBD
    ["MARES-MATCH-PLT", "", "MARE'S MATCH TRANSITION PELLETS", "Pellets", "25LB",
     0, 0, 0, 54.06, 57.03, 1, 2, "", "Non-Purina product - enter cost when known"],
]


def main():
    creds = json.loads(CREDS_JSON)
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet("Inventory")

    print(f"Adding {len(NEW_PRODUCTS)} products...\n")

    rows_to_add = []
    for p in NEW_PRODUCTS:
        print(f"  {p[2]:45s} cost=${p[5]:>7.2f}  pre=${p[8]:>7.2f}  w/tax=${p[9]:>7.2f}  qty={p[10]}")
        rows_to_add.append(p)

    # Get current last row
    all_rows = ws.get_all_values()
    start_row = len(all_rows) + 1

    # Batch append
    ws.update(
        range_name=f"A{start_row}",
        values=rows_to_add,
        value_input_option="USER_ENTERED",
    )

    print(f"\nDone! Added {len(rows_to_add)} products (rows {start_row}-{start_row + len(rows_to_add) - 1}).")
    print("Each has qty=1 as initial stock.")
    print("\nNote: Mare's Match products have cost=$0 - update the Purina Cost column")
    print("      in the sheet or Prices page once you know the supplier cost.")


if __name__ == "__main__":
    main()
