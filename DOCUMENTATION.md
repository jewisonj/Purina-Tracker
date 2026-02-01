# Purina Tracker - Documentation

## Overview

Purina Tracker is a web-based inventory and pricing management system built for a horse feed retail business. It provides daily operational tools for tracking product quantities, managing retail pricing with configurable markups, logging all inventory changes, and importing monthly Purina price list updates.

All data is stored in a shared Google Sheet, eliminating the need for a traditional database. The application is deployed as a single Docker container on Fly.io.

**Live URL**: `https://purina-tracker.fly.dev`

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Architecture](#architecture)
3. [Authentication](#authentication)
4. [Data Model](#data-model)
5. [Google Sheets Integration](#google-sheets-integration)
6. [API Reference](#api-reference)
7. [Frontend](#frontend)
8. [Utility Scripts](#utility-scripts)
9. [Configuration](#configuration)
10. [Deployment](#deployment)
11. [Development Setup](#development-setup)
12. [First-Time Setup](#first-time-setup)

---

## Tech Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| Backend     | Python 3.11, FastAPI, Uvicorn       |
| Frontend    | Vue 3, TypeScript, Vite             |
| UI Library  | PrimeVue 4 (Aura theme)            |
| State Mgmt  | Pinia                              |
| Data Store  | Google Sheets (via gspread)         |
| Auth        | PIN-based login, JWT tokens (PyJWT) |
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

---

## Google Sheets Integration

Google Sheets acts as the database. The backend uses a service account to read/write data via the gspread library.

### Sheet Tabs

**Inventory** - Main product data (one row per product, columns A-N matching the Product model fields above)

**Inventory Log** - Append-only audit trail of every inventory change

**Price List Archive** - Full dump of the most recent Purina CSV for reference

### Caching

Product data is cached in memory for 30 seconds (configurable via `CACHE_TTL_SECONDS`) to reduce Google Sheets API calls. The cache is invalidated on any write operation (inventory adjustments, markup changes, price imports).

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

### Health

| Method | Endpoint  | Auth | Description          |
|--------|-----------|------|----------------------|
| GET    | `/health` | No   | Health check for Fly |

---

## Frontend

### Views

| Route     | View              | Description                                      |
|-----------|-------------------|--------------------------------------------------|
| `/login`  | LoginView         | PIN entry form                                   |
| `/`       | DashboardView     | Main inventory table with quick +/- adjustments  |
| `/prices` | PricesView        | Pricing table with editable markups + CSV import  |
| `/log`    | LogView           | Searchable inventory change history               |

### Dashboard (DashboardView)

The main working view. Shows a curated list of ~36 main products sorted in a hand-picked display order. Features:

- **Search/filter** products by name
- **Quick adjust** buttons (+/-) for fast sales tracking
- **Adjust dialog** for specific adjustment type, quantity, and notes
- **Bulk restock** dialog for entering quantities for multiple products at once
- **Visual indicators**:
  - Red row: product is out of stock (qty = 0)
  - Orange quantity text: product is at or below reorder point

### Prices (PricesView)

Shows all products with pricing details. Features:

- Editable markup percentage per product (changes recalculate prices live)
- Columns: Product Name, Weight, Purina Cost, Markup %, Pre-Tax Price, With-Tax Price, Pallet Cost
- **CSV Import**: Upload a new Purina monthly price list CSV to bulk-update costs

### Log (LogView)

Shows the last 200 inventory changes with:

- Searchable/filterable table
- Color-coded change types (red for sales, green for restocks)
- Timestamp, product, change amount, before/after quantities, who made the change, notes

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
| `CACHE_TTL_SECONDS`      | No       | `30`                      | Google Sheets cache duration         |

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
│   │       ├── pricelist.py     # /pricelist/import
│   │       └── products.py      # /products, markup, reorder
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.ts              # Vue app entry point
│   │   ├── App.vue              # Root component
│   │   ├── style.css            # Global styles
│   │   ├── components/
│   │   │   └── AppLayout.vue    # Nav bar + content wrapper
│   │   ├── views/
│   │   │   ├── LoginView.vue    # PIN login
│   │   │   ├── DashboardView.vue# Inventory management
│   │   │   ├── PricesView.vue   # Pricing & CSV import
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
│   ├── package.json
│   └── vite.config.ts
├── Dockerfile                   # Multi-stage Docker build
├── fly.toml                     # Fly.io deployment config
├── seed.py                      # Sheet initialization script
├── add_products.py              # Add specialty products
├── update_prices.py             # Batch price update script
├── SETUP.md                     # Quick setup guide
└── DOCUMENTATION.md             # This file
```
