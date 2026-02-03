"""Application configuration."""
import os
from functools import lru_cache
from typing import Optional, List

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment-based configuration."""

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Application
    APP_NAME: str = "Behavioral Optimization Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")

    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    ROOT_PATH: str = Field(default="", env="ROOT_PATH")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://user:password@localhost/behaviordb",
        env="DATABASE_URL",
    )
    DATABASE_POOL_SIZE: int = Field(default=20, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=10, env="DATABASE_MAX_OVERFLOW")
    DATABASE_POOL_PRE_PING: bool = Field(default=True, env="DATABASE_POOL_PRE_PING")

    # Redis
    REDIS_URL: Optional[RedisDsn] = Field(default=None, env="REDIS_URL")

    # Security
    SECRET_KEY: str = Field(
        default="your-secret-key-change-this-in-production",
        env="SECRET_KEY",
    )
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    BCRYPT_ROUNDS: int = Field(default=12, env="BCRYPT_ROUNDS")

    # CORS
    CORS_ORIGINS: List[str] | str = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080", "http://localhost:8081"],
        env="CORS_ORIGINS",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")
    CORS_ALLOW_METHODS: List[str] | str = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        env="CORS_ALLOW_METHODS",
    )
    CORS_ALLOW_HEADERS: List[str] | str = Field(
        default=["*"],
        env="CORS_ALLOW_HEADERS",
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60, env="RATE_LIMIT_REQUESTS_PER_MINUTE")

    # Optimization Engine
    OPTIMIZATION_SOLVER: str = Field(default="linear", env="OPTIMIZATION_SOLVER")
    OPTIMIZATION_TIMEOUT_SECONDS: int = Field(default=30, env="OPTIMIZATION_TIMEOUT_SECONDS")
    OPTIMIZATION_TIME_PERIODS: int = Field(default=7, env="OPTIMIZATION_TIME_PERIODS")  # days
    OPTIMIZATION_MIN_SCHEDULE_DURATION: int = Field(default=15, env="OPTIMIZATION_MIN_SCHEDULE_DURATION")  # minutes

    # AI/MCP Integration
    MCP_SERVER_ENABLED: bool = Field(default=False, env="MCP_SERVER_ENABLED")
    MCP_SERVER_HOST: str = Field(default="localhost", env="MCP_SERVER_HOST")
    MCP_SERVER_PORT: int = Field(default=3000, env="MCP_SERVER_PORT")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT",
    )

    # Testing
    TESTING: bool = Field(default=False, env="TESTING")

    @field_validator("CORS_ORIGINS", "CORS_ALLOW_METHODS", "CORS_ALLOW_HEADERS", mode="before")
    @classmethod
    def parse_comma_separated_list(cls, v):
        """Parse comma-separated string or JSON list into a list of strings."""
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    v = json.loads(v)
                except json.JSONDecodeError:
                    pass
            
            if isinstance(v, str):
                return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
