"""Purina Inventory Tracker - FastAPI Backend."""

import hashlib
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, Response

from .config import get_settings
from .routes import auth_router, products_router, inventory_router, pricelist_router, invoices_router
from .sheets import get_sheets_service

settings = get_settings()

app = FastAPI(
    title="Purina Inventory Tracker API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_allow_all else settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(pricelist_router, prefix="/api")
app.include_router(invoices_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Static file serving (production)
STATIC_DIR = Path(__file__).parent.parent / "static"

# Cache for embedded HTML
_html_cache: dict = {"html": None, "etag": None}


def _get_embedded_html() -> tuple[str, str]:
    """Generate HTML with embedded products data. Returns (html, etag)."""
    global _html_cache

    # Read the base index.html
    index_path = STATIC_DIR / "index.html"
    base_html = index_path.read_text(encoding="utf-8")

    # Get products from sheets (uses internal cache)
    try:
        svc = get_sheets_service()
        products = svc.get_all_products()
        products_data = [p.model_dump() for p in products]
    except Exception:
        # If sheets fails, serve without embedded data
        products_data = None

    # Create the embedded script
    if products_data is not None:
        data_json = json.dumps({"products": products_data}, separators=(",", ":"))
        embedded_script = f'<script>window.__INITIAL_DATA__={data_json}</script>'
        # Insert before closing </head> tag
        html = base_html.replace("</head>", f"{embedded_script}</head>")
    else:
        html = base_html

    # Generate ETag from content hash
    etag = hashlib.md5(html.encode()).hexdigest()[:16]

    return html, etag


if STATIC_DIR.exists() and (STATIC_DIR / "index.html").exists():
    if (STATIC_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # Mount public directory for PWA assets (manifest, icons, sw)
    if (STATIC_DIR / "icons").exists():
        app.mount("/icons", StaticFiles(directory=STATIC_DIR / "icons"), name="icons")

    @app.get("/")
    async def serve_index(request: Request):
        """Serve index.html with embedded products data."""
        html, etag = _get_embedded_html()

        # Check If-None-Match header for caching
        if_none_match = request.headers.get("if-none-match", "")
        if if_none_match == etag:
            return Response(status_code=304)

        return HTMLResponse(
            content=html,
            headers={"ETag": etag, "Cache-Control": "no-cache"}
        )

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        if full_path.startswith("api/"):
            return {"detail": "Not found"}
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # For SPA routes, serve embedded HTML
        html, etag = _get_embedded_html()
        return HTMLResponse(
            content=html,
            headers={"ETag": etag, "Cache-Control": "no-cache"}
        )
else:
    @app.get("/")
    async def root():
        return {
            "name": "Purina Inventory Tracker API",
            "version": "1.0.0",
            "docs": "/docs",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
