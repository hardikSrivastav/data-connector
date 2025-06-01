from .main import router as main_router
from .storage import router as storage_router
from .canvas import router as canvas_router

__all__ = ["main_router", "storage_router", "canvas_router"]
