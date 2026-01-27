"""Custom exception hierarchy for the application."""


class BehaviorOptimizationException(Exception):
    """Base exception for the application."""

    def __init__(self, message: str, status_code: int = 500, detail: str = None):
        """Initialize exception."""
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(self.message)


# Authentication Exceptions


class AuthenticationError(BehaviorOptimizationException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed", detail: str = None):
        super().__init__(message, 401, detail)


class AuthorizationError(BehaviorOptimizationException):
    """Raised when user lacks required permissions."""

    def __init__(self, message: str = "Access forbidden", detail: str = None):
        super().__init__(message, 403, detail)


# Resource Exceptions


class ResourceNotFoundError(BehaviorOptimizationException):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found", detail: str = None):
        super().__init__(message, 404, detail)


class ConflictError(BehaviorOptimizationException):
    """Raised when there's a conflict (e.g., duplicate resource)."""

    def __init__(self, message: str = "Conflict", detail: str = None):
        super().__init__(message, 409, detail)


# Optimization Exceptions


class InfeasibleProblemError(BehaviorOptimizationException):
    """Raised when optimization problem is infeasible."""

    def __init__(self, message: str = "Problem is infeasible", detail: str = None):
        super().__init__(message, 422, detail)


class UnboundedProblemError(BehaviorOptimizationException):
    """Raised when optimization problem is unbounded."""

    def __init__(self, message: str = "Problem is unbounded", detail: str = None):
        super().__init__(message, 422, detail)


class SolverTimeoutError(BehaviorOptimizationException):
    """Raised when solver times out."""

    def __init__(self, message: str = "Solver timeout", detail: str = None):
        super().__init__(message, 408, detail)


class SolverError(BehaviorOptimizationException):
    """Raised when solver encounters an error."""

    def __init__(self, message: str = "Solver error", detail: str = None):
        super().__init__(message, 500, detail)


# System Exceptions


class DatabaseError(BehaviorOptimizationException):
    """Raised when database operation fails."""

    def __init__(self, message: str = "Database error", detail: str = None):
        super().__init__(message, 500, detail)


class CacheError(BehaviorOptimizationException):
    """Raised when cache operation fails."""

    def __init__(self, message: str = "Cache error", detail: str = None):
        super().__init__(message, 500, detail)


class RateLimitExceededError(BehaviorOptimizationException):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", detail: str = None):
        super().__init__(message, 429, detail)


# Validation Exceptions


class ValidationError(BehaviorOptimizationException):
    """Raised when validation fails."""

    def __init__(self, message: str = "Validation error", detail: str = None):
        super().__init__(message, 422, detail)


class InvalidConstraintError(BehaviorOptimizationException):
    """Raised when constraint is invalid."""

    def __init__(self, message: str = "Invalid constraint", detail: str = None):
        super().__init__(message, 422, detail)
