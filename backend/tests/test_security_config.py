"""Unit tests for the SECRET_KEY production guard."""
import pytest

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    """Build a Settings instance with the test defaults overridden."""
    base = {
        "SECRET_KEY": "test-secret-key-for-ci-only",
        "ENVIRONMENT": "development",
    }
    base.update(overrides)
    return Settings(**base)


class TestAssertSafeForEnvironment:
    def test_development_with_default_key_passes(self):
        s = _settings(SECRET_KEY="your-secret-key-change-this-in-production", ENVIRONMENT="development")
        s.assert_safe_for_environment()  # must not raise

    def test_production_with_insecure_key_raises(self):
        s = _settings(SECRET_KEY="your-secret-key-change-this-in-production", ENVIRONMENT="production")
        with pytest.raises(RuntimeError, match="insecure SECRET_KEY"):
            s.assert_safe_for_environment()

    def test_production_with_short_key_raises(self):
        s = _settings(SECRET_KEY="too-short", ENVIRONMENT="production")
        with pytest.raises(RuntimeError, match="too short"):
            s.assert_safe_for_environment()

    def test_production_with_empty_key_raises(self):
        s = _settings(SECRET_KEY="", ENVIRONMENT="production")
        with pytest.raises(RuntimeError, match="empty"):
            s.assert_safe_for_environment()

    def test_production_with_strong_key_passes(self):
        s = _settings(
            SECRET_KEY="a" * 64,
            ENVIRONMENT="production",
        )
        s.assert_safe_for_environment()  # must not raise

    def test_prod_alias_also_triggered(self):
        s = _settings(SECRET_KEY="dev-secret-key-change-in-production", ENVIRONMENT="prod")
        with pytest.raises(RuntimeError):
            s.assert_safe_for_environment()
