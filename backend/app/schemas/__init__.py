"""API schemas."""
from .user import (
    UserRegistration,
    UserLogin,
    UserUpdate,
    UserResponse,
    AuthResponse,
    TokenRefreshRequest,
    TokenRefreshResponse,
)
from .behavior import (
    BehaviorCreate,
    BehaviorUpdate,
    BehaviorResponse,
    BehaviorListResponse,
    BehaviorStatistics,
    BehaviorImpacts,
)
from .optimization import (
    OptimizationRequest,
    OptimizationResult,
    OptimizationSummary,
    OptimizationHistoryResponse,
    ScheduledBehaviorResponse,
    ObjectiveContributionsResponse,
    InfeasibilityDiagnostics,
)
from .common import (
    ErrorResponse,
    SuccessResponse,
    PaginationParams,
    HealthCheckResponse,
)

__all__ = [
    "UserRegistration",
    "UserLogin",
    "UserUpdate",
    "UserResponse",
    "AuthResponse",
    "TokenRefreshRequest",
    "TokenRefreshResponse",
    "BehaviorCreate",
    "BehaviorUpdate",
    "BehaviorResponse",
    "BehaviorListResponse",
    "BehaviorStatistics",
    "BehaviorImpacts",
    "OptimizationRequest",
    "OptimizationResult",
    "OptimizationSummary",
    "OptimizationHistoryResponse",
    "ScheduledBehaviorResponse",
    "ObjectiveContributionsResponse",
    "InfeasibilityDiagnostics",
    "ErrorResponse",
    "SuccessResponse",
    "PaginationParams",
    "HealthCheckResponse",
]
