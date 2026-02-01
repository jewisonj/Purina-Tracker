"""Update retail prices in the Google Sheet from the existing price list."""

import json
import os

from dotenv import load_dotenv
import gspread

load_dotenv("J:/Purina-Tracker/backend/.env")

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
CREDS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

# Retail prices from the user's current price list
# Format: (sheet_row, product_name, pre_tax, with_tax)
PRICES = [
    (9,  "EQUINE SENIOR",                    27.72, 29.24),
    (10, "EQUINE SENIOR ACTIVE",             29.49, 31.11),
    (48, "STRATEGY GX BAG.",                 23.99, 25.31),
    (50, "STRATEGY HEALTHY EDGE",            24.11, 25.44),
    (52, "ULTIUM GASTRIC CARE FORMULA",      31.96, 33.72),
    (53, "ULTIUM GROWTH FORMULA",            32.42, 34.20),
    (51, "ULTIUM COMP HORSE FORMULA",        32.59, 34.38),
    (22, "IMPACT PROFESSIONAL SENIOR",       22.91, 24.17),
    (20, "IMPACT PROFESSIONAL MARE+FOAL",    23.18, 24.45),
    (21, "IMPACT PROFESSIONAL PERFORM",      25.21, 26.60),
    (15, "IMPACT ALL STAGES 12-6 TXT",       18.86, 19.90),
    (18, "IMPACT HAY STRETCHER",             16.70, 17.62),
    (29, "OMOLENE 200 PERFORMANCE",          25.58, 26.99),
    (30, "OMOLENE 300 MARE+FOAL",            25.49, 26.89),
    (31, "OMOLENE 400 50LB",                 25.49, 26.89),
    (55, "WELLSOLVE L/S",                    37.05, 39.09),
    (43, "PURINA MINI-HORSE+PONY",           26.21, 27.65),
    (6,  "ENRICH PLUS",                      36.08, 38.06),
    (26, "OMEGA MATCH HORSE RATION BAL",     43.50, 45.89),
    (12, "FREE BALANCE 12-12 SUPPLEMENT",    36.65, 38.67),
    (46, "REPLENIMASH 25LB",                 36.21, 38.20),
    (2,  "AMPLIFY EQUINE SUPPLEMENT BG",     60.54, 63.87),
    (33, "OUTLAST GASTRIC SUPPORT SUPP",     43.02, 45.39),
    (44, "PURINA SUPERSPORT 25LB",           47.64, 50.26),
    (35, "PUR EQUITUB CLARIFLY 55LB",        70.74, 74.63),
    (34, "PUR EQUITUB CLARIFLY 125LB",      148.25, 156.40),
]


def main():
    creds = json.loads(CREDS_JSON)
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet("Inventory")

    rows = ws.get_all_values()
    print(f"Updating {len(PRICES)} products using batch update...\n")

    # Build batch update data
    batch_updates = []
    for row_num, name, pre_tax, with_tax in PRICES:
        row = rows[row_num - 1]
        sheet_name = row[2]
        cost = float(row[5] or 0)

        if name.upper() not in sheet_name.upper() and sheet_name.upper() not in name.upper():
            print(f"  WARNING: Row {row_num} mismatch! Expected '{name}', got '{sheet_name}' - SKIPPING")
            continue

        markup = round((pre_tax / cost) - 1, 4) if cost > 0 else 0.25

        # Columns H, I, J = columns 8, 9, 10 = range H{row}:J{row}
        batch_updates.append({
            "range": f"H{row_num}:J{row_num}",
            "values": [[markup, pre_tax, with_tax]],
        })
        print(f"  {sheet_name:45s} cost=${cost:>7.2f}  markup={markup*100:>5.1f}%  pre=${pre_tax:>7.2f}  w/tax=${with_tax:>7.2f}")

    # Single batch update call
    ws.batch_update(batch_updates, value_input_option="USER_ENTERED")

    print(f"\nDone! Updated {len(batch_updates)} products in one batch.")
    print("\nProducts NOT updated (case packs or not in sheet):")
    print("  - Omega Match Ahiflower Oil Supplement - sheet only has case packs")
    print("  - Systemiq Probiotic Supplement - sheet only has 6x2LB case")
    print("  - RepleniMash 7LB - sheet only has 4x7LB case")
    print("  - Mare's Match Foal Milk Replacer - not in Purina CSV")
    print("  - Mare's Match Transition Pellets - not in Purina CSV")
    print("  - Apple and Oat-Flavored Horse treats - sheet has 15LB / 6-pack")
    print("  - Nicker Makers Horse Treats - sheet has 15LB / 6-pack")
    print("  - Outlast Horse Treats - sheet has 6x3.5LB pack")


if __name__ == "__main__":
    main()
