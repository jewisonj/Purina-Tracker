# Purina Inventory Tracker - Setup Guide

## 1. Google Cloud Service Account

You need a Google Cloud service account so the app can read/write your Google Sheet.

### Create the service account:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one) - name it something like `purina-tracker`
3. Enable the **Google Sheets API**:
   - Go to "APIs & Services" > "Library"
   - Search for "Google Sheets API"
   - Click "Enable"
4. Create a service account:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "Service account"
   - Name: `purina-tracker`
   - Click "Create and Continue" > "Done"
5. Create a key:
   - Click on the service account you just created
   - Go to the "Keys" tab
   - Click "Add Key" > "Create new key" > JSON
   - Save the downloaded JSON file as `service-account.json` in this project folder
   - **Never commit this file to git** (it's in .gitignore)

### Share the Google Sheet:

1. Open the service account JSON file and copy the `client_email` value (looks like `purina-tracker@project-name.iam.gserviceaccount.com`)
2. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1fTIf-pbn0zeihe6PSGaeD_EhSOo3S7JMJK-OxYkLrjE
3. Click "Share" and add the service account email as an **Editor**

## 2. Local Development Setup

### Backend:

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
```

Create `backend/.env`:
```
GOOGLE_SHEET_ID=1fTIf-pbn0zeihe6PSGaeD_EhSOo3S7JMJK-OxYkLrjE
GOOGLE_CREDENTIALS_JSON=<paste entire service-account.json contents on one line>
APP_PIN=1234
JWT_SECRET=local-dev-secret
DEBUG=true
CORS_ALLOW_ALL=true
API_PORT=8002
```

**Tip:** To get the JSON on one line, you can run:
```bash
python -c "import json; print(json.dumps(json.load(open('service-account.json'))))"
```

Run the backend:
```bash
cd backend
python -m uvicorn app.main:app --reload --port 8002
```

### Frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on `http://localhost:5175` and proxies API requests to the backend on port 8002.

## 3. Seed the Google Sheet

Before using the app, seed the sheet with products from the Purina CSV:

```bash
# From the project root (with backend venv activated)
python seed.py
```

This creates three tabs in your Google Sheet:
- **Inventory** - All ~54 products with pricing columns
- **Inventory Log** - Empty, ready for change tracking
- **Price List Archive** - Full Purina CSV dump for reference

## 4. Deploy to Fly.io

### First time:

```bash
fly apps create purina-tracker
```

### Set secrets:

```bash
fly secrets set APP_PIN=your-secure-pin
fly secrets set JWT_SECRET=your-random-secret-string
fly secrets set GOOGLE_SHEET_ID=1fTIf-pbn0zeihe6PSGaeD_EhSOo3S7JMJK-OxYkLrjE
fly secrets set GOOGLE_CREDENTIALS_JSON='<paste JSON on one line>'
```

### Deploy:

```bash
fly deploy
```

The app will be available at `https://purina-tracker.fly.dev`

## 5. First Use

1. Open the app and log in with your PIN
2. Go through each product and enter your current bag count (the +/- buttons or Adjust dialog)
3. Set markup % for each product on the Prices page (defaults to 25%)
4. You're ready to go! Use the dashboard daily for quick inventory lookups and adjustments.

## Updating Prices

When you get a new monthly price list from Purina:
1. Go to the Prices page
2. Click "Import CSV"
3. Upload the new CSV file
4. The app will update costs for existing products and add any new ones
