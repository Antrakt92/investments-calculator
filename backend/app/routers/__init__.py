from .upload import router as upload_router
from .portfolio import router as portfolio_router
from .tax import router as tax_router
from .persons import router as persons_router

__all__ = ["upload_router", "portfolio_router", "tax_router", "persons_router"]
