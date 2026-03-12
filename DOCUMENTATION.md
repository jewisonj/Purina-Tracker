# Purina Tracker - Documentation

## Overview

Purina Tracker is a web-based inventory and pricing management system built for a horse feed retail business. It provides daily operational tools for tracking product quantities, managing retail pricing with configurable markups, logging all inventory changes, and importing monthly Purina price list updates.

All data is stored in a shared Google Sheet, eliminating the need for a traditional database. The application is deployed as a single Docker container on Fly.io.

**Live URL**: `https://purina-tracker.fly.dev`

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Architecture](#architecture)
3. [Performance Optimizations](#performance-optimizations)
4. [PWA Support](#pwa-support)
5. [Authentication](#authentication)
6. [Data Model](#data-model)
7. [Google Sheets Integration](#google-sheets-integration)
8. [API Reference](#api-reference)
9. [Frontend](#frontend)
10. [Utility Scripts](#utility-scripts)
11. [Configuration](#configuration)
12. [Deployment](#deployment)
13. [Development Setup](#development-setup)
14. [First-Time Setup](#first-time-setup)

---

## Tech Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| Backend     | Python 3.11, FastAPI, Uvicorn       |
| Frontend    | Vue 3, TypeScript, Vite             |
| UI Library  | PrimeVue 4 (Aura theme)            |
| State Mgmt  | Pinia                              |
| Data Store  | Google Sheets (via gspread)         |
| File Storage| Google Drive (invoice PDFs)         |
| PDF Tools   | pypdf, reportlab (watermarking)     |
| Auth        | PIN-based login, JWT tokens (PyJWT) |
| PWA         | vite-plugin-pwa, Workbox            |
| Deployment  | Docker, Fly.io                      |

---

## Architecture

```
                +-----------+
                |  Browser  |
                +-----+-----+
                      |
                      | HTTPS
                      v
            +-------------------+
            |     Fly.io CDN    |
            +-------------------+
                      |
                      v
         +-------------------------+
         |   Docker Container      |
         |                         |
         |  +-------------------+  |
         |  | Uvicorn (port 8080)| |
         |  +-------------------+  |
         |  | FastAPI Backend   |  |
         |  |   /api/*  routes  |  |
         |  |   /*  static files|  |
         |  +--------+----------+  |
         +-----------|-------------+
                     |
                     | Google Sheets API
                     v
            +------------------+
            |  Google Sheets   |
            |  (Data Store)    |
            +------------------+
```

The application runs as a single container. FastAPI serves the backend API at `/api/*` and the Vue frontend as static files at all other routes. In development, the frontend runs on its own Vite dev server with a proxy to the backend.

---

## Performance Optimizations

The app is optimized for fast initial load through several techniques:

### Embedded Data in HTML

Instead of making an API call to fetch products on page load, product data is embedded directly in the HTML:

1. When serving `index.html`, FastAPI reads current product data from the Google Sheets cache
2. The data is serialized as JSON and injected as `<script>window.__INITIAL_DATA__={...}</script>`
3. The frontend checks for `window.__INITIAL_DATA__` on mount and uses it immediately
4. This eliminates the initial API roundtrip, reducing load time from ~2-3s to under 500ms

**ETag Caching**: The embedded HTML response includes an ETag header based on the content hash. Browsers can make conditional requests (`If-None-Match`) and receive `304 Not Modified` responses when data hasn't changed.

### Backend Caching

- Product data is cached in memory for **5 minutes** (300 seconds)
- Cache is invalidated on write operations (inventory adjustments, markup changes)
- Background operations (like PDF watermarking) don't block the main request

### Frontend Optimizations

- Initial data loads instantly from embedded script
- Subsequent refreshes still use the API for real-time updates
- Service worker caches static assets (JS, CSS, fonts, icons)

---

## PWA Support

The app is installable as a Progressive Web App on desktop and mobile devices.

### Features

- **Installable**: "Add to Home Screen" prompt on supported devices
- **Offline Assets**: Static assets (JS, CSS, icons) are cached by the service worker
- **App-like Experience**: Standalone display mode without browser chrome
- **Purina Branding**: Custom icons and theme color (#C41230)

### Configuration

**Manifest** (`frontend/public/manifest.json`):
```json
{
  "name": "Purina Tracker",
  "short_name": "Purina",
  "theme_color": "#C41230",
  "background_color": "#1a1a1a",
  "display": "standalone",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192" },
    { "src": "/icons/icon-512.png", "sizes": "512x512" }
  ]
}
```

**Service Worker**: Generated by `vite-plugin-pwa` using Workbox. Configured in `vite.config.ts`:
- Precaches all build assets (JS, CSS, HTML, icons)
- Runtime caching for API responses (network-first with 5-minute TTL)
- Auto-updates when new version is deployed

### Installation

- **Chrome/Edge Desktop**: Click the install icon in the address bar
- **Android Chrome**: Banner appears automatically or use menu → "Add to Home Screen"
- **iOS Safari**: Share → "Add to Home Screen"

---

## Authentication

The app uses a simple PIN + JWT token system.

### Login Flow

1. User enters a numeric PIN on the login page
2. Frontend sends `POST /api/auth/login` with the PIN
3. Backend compares against the `APP_PIN` environment variable
4. On match, a JWT token is created (HS256, 7-day expiry)
5. Token is stored in the browser's `localStorage`
6. All subsequent API requests include the token as `Authorization: Bearer <token>`

### Token Expiry

Tokens are valid for 7 days (configurable via `JWT_EXPIRY_DAYS`). When a token expires or is invalid, the API returns `401`, the frontend clears the token, and redirects the user to the login page.

### Protected Routes

All API endpoints require authentication except:
- `GET /health` - health check
- `POST /api/auth/login` - login

All frontend routes except `/login` require authentication. Unauthenticated users are redirected to `/login`.

---

## Data Model

### Product

| Field            | Type    | Description                                  |
|------------------|---------|----------------------------------------------|
| `material_no`    | string  | Purina material number (unique identifier)   |
| `formula_code`   | string  | Purina formula code                          |
| `product_name`   | string  | Full product name                            |
| `product_form`   | string  | Form factor (Pellets, Powder, Liquid, etc.)  |
| `unit_weight`    | string  | Package size (50LB, 25LB, etc.)              |
| `purina_cost`    | float   | Cost per unit from Purina                    |
| `pallet_cost`    | float   | Full pallet cost                             |
| `markup_pct`     | float   | Markup percentage (e.g., 0.25 = 25%)         |
| `retail_pre_tax` | float   | Calculated retail price before tax            |
| `retail_with_tax`| float   | Calculated retail price with 5.5% sales tax  |
| `qty_on_hand`    | int     | Current inventory count                      |
| `reorder_point`  | int     | Low-stock alert threshold                    |
| `last_updated`   | string  | Timestamp of last change                     |
| `notes`          | string  | Optional notes                               |

### Inventory Adjustment

| Field         | Type   | Description                               |
|---------------|--------|-------------------------------------------|
| `material_no` | string | Product to adjust                         |
| `change_type` | string | `sale`, `restock`, or `adjustment`        |
| `quantity`    | int    | Positive to add, negative to subtract      |
| `notes`       | string | Optional notes                            |

### Log Entry

| Field          | Type   | Description                  |
|----------------|--------|------------------------------|
| `timestamp`    | string | When the change occurred     |
| `product_name` | string | Product name                 |
| `material_no`  | string | Product identifier           |
| `change_type`  | string | Type of change               |
| `qty_changed`  | int    | Amount changed               |
| `previous_qty` | int    | Quantity before change       |
| `new_qty`      | int    | Quantity after change        |
| `changed_by`   | string | Who made the change          |
| `notes`        | string | Additional notes             |

### Invoice

| Field           | Type   | Description                              |
|-----------------|--------|------------------------------------------|
| `invoice_number`| string | Auto-generated invoice number (INV-XXXX) |
| `date`          | string | Invoice date                             |
| `customer`      | string | Customer name                            |
| `items_summary` | string | Compact summary of line items            |
| `total`         | string | Invoice total (formatted with $)         |
| `paid`          | bool   | Payment status                           |
| `filed_at`      | string | Timestamp when invoice was filed         |
| `drive_url`     | string | Google Drive URL to the PDF              |

---

## Google Sheets Integration

Google Sheets acts as the database. The backend uses a service account to read/write data via the gspread library.

### Sheet Tabs

**Inventory** - Main product data (one row per product, columns A-N matching the Product model fields above)

**Inventory Log** - Append-only audit trail of every inventory change

**Price List Archive** - Full dump of the most recent Purina CSV for reference

**Invoices** - Filed invoice records with columns: Invoice #, Date, Customer, Items Summary, Total, Paid, Filed At, Drive URL

### Caching

Product data is cached in memory for **5 minutes** (300 seconds, configurable via `CACHE_TTL_SECONDS`) to reduce Google Sheets API calls. The cache is invalidated on any write operation (inventory adjustments, markup changes, price imports).

### Pricing Calculation

Retail prices are calculated using ceil-to-quarter rounding (prices round up to the nearest $0.25):

```
retail_pre_tax  = ceil_to_quarter(purina_cost * (1 + markup_pct))
retail_with_tax = ceil_to_quarter(retail_pre_tax * 1.055)
```

The tax rate is 5.5%.

---

## API Reference

Base URL: `/api`

### Authentication

| Method | Endpoint         | Auth | Description            |
|--------|------------------|------|------------------------|
| POST   | `/auth/login`    | No   | Login with PIN         |
| GET    | `/auth/verify`   | Yes  | Verify token is valid  |

**POST /auth/login**
```json
// Request
{ "pin": "1234" }

// Response
{ "token": "eyJ...", "expires_in_days": 7 }
```

### Products

| Method | Endpoint                           | Auth | Description               |
|--------|------------------------------------|------|---------------------------|
| GET    | `/products`                        | Yes  | List all products         |
| PUT    | `/products/{material_no}/markup`   | Yes  | Update markup percentage  |
| PUT    | `/products/{material_no}/reorder`  | Yes  | Update reorder point      |

**PUT /products/{material_no}/markup**
```json
// Request
{ "markup_pct": 0.30 }

// Response - Updated product object
```

### Inventory

| Method | Endpoint                | Auth | Description                          |
|--------|-------------------------|------|--------------------------------------|
| POST   | `/inventory/adjust`     | Yes  | Adjust a single product's quantity   |
| POST   | `/inventory/bulk-adjust`| Yes  | Adjust multiple products at once     |
| GET    | `/inventory/log`        | Yes  | Get inventory change history         |
| GET    | `/inventory/low-stock`  | Yes  | Get products at or below reorder pt  |

**POST /inventory/adjust**
```json
// Request
{
  "material_no": "0046538",
  "change_type": "sale",
  "quantity": -2,
  "notes": "Walk-in customer"
}

// Response - Updated product object
```

**GET /inventory/log?limit=100**
- `limit` query parameter (default: 100, max: 500)
- Returns entries in reverse chronological order

### Price List

| Method | Endpoint             | Auth | Description                     |
|--------|----------------------|------|---------------------------------|
| POST   | `/pricelist/import`  | Yes  | Import Purina CSV price list    |

**POST /pricelist/import**
- Content-Type: `multipart/form-data`
- Body: CSV file
- Filters for HORSE products and "CA ALL STOCK" from ALL PURPOSE
- Updates existing products and adds new ones (default 25% markup)

```json
// Response
{
  "updated": 42,
  "new_products": ["New Product Name"],
  "message": "Updated 42 products, added 1 new"
}
```

### Invoices

| Method | Endpoint                          | Auth | Description                      |
|--------|-----------------------------------|------|----------------------------------|
| GET    | `/invoices`                       | Yes  | List all filed invoices          |
| POST   | `/invoices/file`                  | Yes  | File a new invoice with PDF      |
| PUT    | `/invoices/{invoice_number}/status`| Yes | Update paid status               |

**GET /invoices**
- Optional query param: `?q=searchterm` to filter by customer or invoice number
- Returns list of all invoices in reverse chronological order

```json
// Response
{
  "invoices": [
    {
      "invoice_number": "INV-0042",
      "date": "2024-01-15",
      "customer": "Smith Ranch",
      "items_summary": "SafeChoice Perform x2; Equine Senior x1",
      "total": "$125.50",
      "paid": true,
      "filed_at": "2024-01-15 14:30:00",
      "drive_url": "https://drive.google.com/file/d/..."
    }
  ],
  "total": 1
}
```

**POST /invoices/file**
- Content-Type: `multipart/form-data`
- Body: `invoice_data` (JSON string) + `pdf` (file)
- Logs invoice to Google Sheets and uploads PDF to Google Drive

```json
// Response
{
  "message": "Invoice filed successfully",
  "drive_url": "https://drive.google.com/file/d/...",
  "invoice_number": "INV-0042"
}
```

**PUT /invoices/{invoice_number}/status**
- Updates the paid status of an invoice
- When marking as paid, queues a background task to add a "PAID" watermark to the PDF

```json
// Request
{ "paid": true }

// Response
{
  "message": "Invoice INV-0042 marked as Paid",
  "paid": true,
  "watermark_queued": true
}
```

**PAID Watermark**: When an invoice is marked as paid, a semi-transparent red "PAID" watermark is added to every page of the PDF in Google Drive. This runs as a non-blocking background task using FastAPI's `BackgroundTasks`, so the API response returns immediately.

### Health

| Method | Endpoint  | Auth | Description          |
|--------|-----------|------|----------------------|
| GET    | `/health` | No   | Health check for Fly |

---

## Frontend

### Theme

The app uses a **dark theme** with Purina red (`#c41230`) accents. PrimeVue's Aura preset is configured with a red primary palette and dark mode enabled via a `.dark-mode` CSS class on the root `<html>` element. All custom styles use CSS custom properties defined in `style.css` for consistent dark surfaces, borders, and text colors.

### Views

| Route       | View              | Description                                           |
|-------------|-------------------|-------------------------------------------------------|
| `/login`    | LoginView         | PIN entry form                                        |
| `/`         | DashboardView     | Main inventory table with search and quick +/- adjust |
| `/invoice`  | InvoiceView       | Invoice builder with PDF export and inventory pull     |
| `/invoices` | InvoicesView      | Invoice records with paid status toggle (Admin only)   |
| `/prices`   | PricesView        | Dealer price list viewer + CSV import                  |
| `/log`      | LogView           | Searchable inventory change history                    |

### Dashboard (DashboardView)

The main working view. Shows a curated list of ~36 main products organized into groups. Features:

- **Search/filter bar** with multi-term matching (e.g., "safe 50" matches "SafeChoice Perform 50LB")
- **Quick adjust** buttons (+/-) on each row for fast sales/restock tracking
- **Product groups** separated by visual dividers, groups with no search matches are hidden
- **Visual indicators**:
  - Dark red row: product is out of stock (qty = 0)
  - Dark amber row: product is at or below reorder point

### Invoice (InvoiceView)

A card-based invoice builder for creating customer invoices. Features:

- **Customer name** and **date** fields
- **Line item cards** that auto-expand as products are added (card-based layout, not a table)
- **Product selector** dropdown with search/filter
- **Qty stepper** buttons (+/-) on each line item
- **Auto-calculated** unit price, extended price, and invoice total
- **Download PDF** button generates a professional invoice PDF (jsPDF + autoTable)
- **Pull Inventory** button deducts all line item quantities from inventory via bulk adjust, logging each as a sale
- **Paid** checkbox for tracking payment status
- **Clear** button resets the entire invoice

### Prices (PricesView)

Shows the full Purina dealer price list archive from the Google Sheet. Features:

- Searchable/filterable DataTable across all columns
- **CSV Import**: Upload a new Purina monthly price list CSV to refresh costs

### Log (LogView)

Shows the last 200 inventory changes with:

- Searchable/filterable table
- Color-coded change types (red for sales, green for restocks)
- Timestamp, product, change amount, before/after quantities, who made the change, notes

### Records (InvoicesView)

Admin-only view showing all filed invoices. Navigation tab labeled "Records" to distinguish from "Invoice" (create). Features:

- **DataTable** with columns: Invoice #, Date, Customer, Items Summary, Total, Status, Actions
- **Search bar** to filter by customer name or invoice number
- **Status badge**: Green "Paid" or amber "Unpaid"
- **Toggle button**: Mark invoice as Paid/Unpaid with one click
- **View PDF button**: Opens the invoice PDF in Google Drive
- **Background watermarking**: When marked as paid, a "PAID" watermark is added to the PDF in the background

### State Management (Pinia Stores)

**Auth Store** (`stores/auth.ts`)
- Manages authentication state
- Checks localStorage for existing token on app load
- Verifies token validity with backend

**Inventory Store** (`stores/inventory.ts`)
- Holds product list and log entries
- Provides computed properties: `lowStockProducts`, `totalProducts`, `lowStockCount`
- All data-fetching and mutation methods

---

## Utility Scripts

These scripts are run manually from the command line, not through the web app.

### seed.py

**Purpose**: One-time initialization of the Google Sheet.

- Reads a Purina CSV price list
- Filters for horse feed products
- Creates three tabs (Inventory, Inventory Log, Price List Archive)
- Populates products with default 25% markup, reorder point of 5, and qty of 0
- Run once before first use

```bash
python seed.py
```

### add_products.py

**Purpose**: Add specialty products that aren't in the standard Purina CSV.

- Adds individual unit sales from case packs (e.g., single bottles from a 4-pack)
- Adds horse treats sold per bag from 6-packs
- Adds non-Purina products (Mare's Match)

```bash
python add_products.py
```

### update_prices.py

**Purpose**: Batch update prices from a hard-coded list.

- Updates pre-tax and with-tax prices for ~26 main products
- Back-calculates markup percentages
- Used when prices are set manually outside the normal CSV import flow

```bash
python update_prices.py
```

---

## Configuration

All configuration is via environment variables. In development, use a `.env` file in the `backend/` directory.

| Variable                 | Required | Default                   | Description                          |
|--------------------------|----------|---------------------------|--------------------------------------|
| `GOOGLE_SHEET_ID`        | Yes      | -                         | Google Sheet spreadsheet ID          |
| `GOOGLE_CREDENTIALS_JSON`| Yes      | -                         | Service account JSON (as string)     |
| `APP_PIN`                | No       | `1234`                    | Login PIN                            |
| `JWT_SECRET`             | No       | (generated)               | JWT signing secret                   |
| `JWT_EXPIRY_DAYS`        | No       | `7`                       | Token lifetime in days               |
| `API_HOST`               | No       | `0.0.0.0`                 | Server bind address                  |
| `API_PORT`               | No       | `8080`                    | Server port                          |
| `DEBUG`                  | No       | `false`                   | Enable debug mode                    |
| `CORS_ALLOW_ALL`         | No       | `false`                   | Allow all CORS origins               |
| `CORS_ORIGINS`           | No       | `http://localhost:5175`   | Comma-separated allowed origins      |
| `CACHE_TTL_SECONDS`      | No       | `300`                     | Google Sheets cache duration (5 min) |

---

## Deployment

### Production (Fly.io)

The app is deployed as a single Docker container on Fly.io.

**Fly.io settings** (`fly.toml`):
- Region: `ord` (Chicago)
- VM: 256MB RAM, 1 shared CPU
- Auto-scaling: 0-1 machines (scales to zero when idle)
- Health check: `GET /health` every 30 seconds
- HTTPS enforced

**Docker build** (`Dockerfile`):
1. Stage 1: Build frontend with Node 20 (`npm run build`)
2. Stage 2: Python 3.11 slim, install backend dependencies, copy frontend build as static files, run Uvicorn on port 8080

### Deploy Commands

```bash
# First-time setup
fly apps create purina-tracker
fly secrets set APP_PIN=<pin> JWT_SECRET=<secret> GOOGLE_SHEET_ID=<id> GOOGLE_CREDENTIALS_JSON='<json>'

# Deploy
fly deploy

# View logs
fly logs

# SSH into container
fly ssh console
```

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- A Google Cloud service account with Sheets API access
- The service account JSON key file

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

Create `backend/.env`:
```env
GOOGLE_SHEET_ID=your_sheet_id
GOOGLE_CREDENTIALS_JSON={"type":"service_account",...}
APP_PIN=1234
JWT_SECRET=dev-secret-change-in-prod
DEBUG=true
CORS_ALLOW_ALL=true
```

Start the backend:
```bash
python -m uvicorn app.main:app --reload --port 8002
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5175` and proxies `/api` requests to the backend at `http://localhost:8002`.

---

## First-Time Setup

1. **Create a Google Cloud project** and enable the Google Sheets API
2. **Create a service account** and download the JSON key
3. **Create a new Google Sheet** and share it with the service account email (Editor access)
4. **Set environment variables** with the Sheet ID and credentials JSON
5. **Run `seed.py`** to initialize the sheet with products from a Purina CSV
6. **Run `add_products.py`** (optional) to add specialty products
7. **Deploy** or start the dev server
8. **Log in** with your PIN and do an initial physical inventory count
9. **Set markup percentages** for each product on the Prices page

---

## Project Structure

```
Purina-Tracker/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── auth.py              # JWT token creation & verification
│   │   ├── config.py            # Pydantic settings / env vars
│   │   ├── main.py              # FastAPI app, CORS, static files
│   │   ├── models.py            # Pydantic data models
│   │   ├── sheets.py            # Google Sheets read/write operations
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py          # /auth/login, /auth/verify
│   │       ├── inventory.py     # /inventory/adjust, /log, /low-stock
│   │       ├── invoices.py      # /invoices (list, file, status)
│   │       ├── pricelist.py     # /pricelist/import
│   │       └── products.py      # /products, markup, reorder
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.ts              # Vue app entry point (PrimeVue dark theme config)
│   │   ├── App.vue              # Root component
│   │   ├── style.css            # Global dark theme styles & CSS variables
│   │   ├── components/
│   │   │   └── AppLayout.vue    # Nav bar + content wrapper
│   │   ├── config/
│   │   │   └── products.ts      # Product display groups & ordering
│   │   ├── views/
│   │   │   ├── LoginView.vue    # PIN login
│   │   │   ├── DashboardView.vue# Inventory management with search
│   │   │   ├── InvoiceView.vue  # Invoice builder with PDF & inventory pull
│   │   │   ├── InvoicesView.vue # Invoice records with paid toggle
│   │   │   ├── PricesView.vue   # Dealer price list & CSV import
│   │   │   └── LogView.vue      # Change history
│   │   ├── stores/
│   │   │   ├── auth.ts          # Auth state
│   │   │   └── inventory.ts     # Product & log state
│   │   ├── services/
│   │   │   └── api.ts           # API client
│   │   ├── types/
│   │   │   └── index.ts         # TypeScript interfaces
│   │   └── router/
│   │       └── index.ts         # Route definitions
│   ├── public/
│   │   ├── manifest.json        # PWA manifest
│   │   └── icons/               # PWA icons (192x192, 512x512)
│   ├── package.json
│   └── vite.config.ts           # Includes PWA plugin config
├── Dockerfile                   # Multi-stage Docker build
├── fly.toml                     # Fly.io deployment config
├── seed.py                      # Sheet initialization script
├── add_products.py              # Add specialty products
├── update_prices.py             # Batch price update script
├── SETUP.md                     # Quick setup guide
└── DOCUMENTATION.md             # This file
```
