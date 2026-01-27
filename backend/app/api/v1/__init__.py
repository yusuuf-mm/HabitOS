"""API routes."""
from .auth import router as auth_router
from .behaviors import router as behaviors_router
from .optimization import router as optimization_router

__all__ = ["auth_router", "behaviors_router", "optimization_router"]
