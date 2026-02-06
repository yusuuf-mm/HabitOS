"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core import settings, BehaviorOptimizationException
from app.core.exceptions import ValidationError, DatabaseError
from app.db.database import init_db, close_db
from app.api.v1 import (
    auth_router,
    behaviors_router,
    optimization_router,
    schedule_router,
    analytics_router,
)
from app.schemas import HealthCheckResponse, ErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    # await init_db()  # Disabled: Use Alembic migrations for database schema management
    # logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down application")
    await close_db()
    logger.info("Database connection closed")


# Create application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Operations Research + AI Engineering for Behavioral Optimization",
    lifespan=lifespan,
)

# CORS middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )


# Exception handlers
@app.exception_handler(BehaviorOptimizationException)
async def behavior_optimization_exception_handler(
    request: Request, exc: BehaviorOptimizationException
):
    """Handle custom exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "detail": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "ValidationError",
            "detail": exc.detail,
            "status_code": 422,
        },
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity errors."""
    logger.error(f"Database integrity error: {str(exc)}")
    return JSONResponse(
        status_code=409,
        content={
            "error": "ConflictError",
            "detail": "Resource already exists or conflicts with existing data",
            "status_code": 409,
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors."""
    logger.error(f"Database error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "DatabaseError",
            "detail": "Database operation failed",
            "status_code": 500,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "detail": "An unexpected error occurred",
            "status_code": 500,
        },
    )


# Routes
@app.get("/", tags=["health"])
async def root():
    """Root endpoint with API info."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/api/health", response_model=HealthCheckResponse, tags=["health"])
async def health_check():
    """Health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        database="connected",
    )


# API routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(behaviors_router, prefix="/api/v1")
app.include_router(optimization_router, prefix="/api/v1")
app.include_router(schedule_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
