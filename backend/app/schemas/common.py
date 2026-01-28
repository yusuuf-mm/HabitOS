"""Common schemas."""
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    status_code: int
    detail: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None


class SuccessResponse(BaseModel):
    """Success response."""

    message: str
    data: Optional[Any] = None


class PaginationParams(BaseModel):
    """Pagination parameters."""

    skip: int = Field(0, ge=0)
    limit: int = Field(10, ge=1, le=100)

    @property
    def offset(self) -> int:
        """Get offset for database queries."""
        return self.skip


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str
    environment: str
    database: str = "connected"
