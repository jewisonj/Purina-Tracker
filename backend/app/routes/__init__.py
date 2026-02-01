from .auth import router as auth_router
from .products import router as products_router
from .inventory import router as inventory_router
from .pricelist import router as pricelist_router
from .invoices import router as invoices_router

__all__ = ["auth_router", "products_router", "inventory_router", "pricelist_router", "invoices_router"]
