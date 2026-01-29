"""API routes."""
from .auth import router as auth_router
from .behaviors import router as behaviors_router
from .optimization import router as optimization_router
from .schedule import router as schedule_router
from .analytics import router as analytics_router

__all__ = [
    "auth_router",
    "behaviors_router",
    "optimization_router",
    "schedule_router",
    "analytics_router",
]
