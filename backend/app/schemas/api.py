"""Common API response schemas."""
from datetime import datetime, timezone
from typing import TypeVar, Generic, Optional, Any
from pydantic import BaseModel, Field

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ErrorDetail(BaseModel):
    """Error detail information."""
    code: str
    message: str
    details: Optional[Any] = None

class ErrorResponse(ApiResponse):
    """Standard error response."""
    success: bool = False
    error: ErrorDetail
