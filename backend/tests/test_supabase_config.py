"""Supabase-aware settings, with the helper model split left unchanged."""
from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "SECRET_KEY": "test-secret-key-for-ci-only",
        "ENVIRONMENT": "development",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/behaviordb",
        "DATABASE_DISABLE_PREPARED_STATEMENTS": False,
        "_env_file": None,
    }
    base.update(overrides)
    return Settings(**base)


def test_plain_postgres_url_is_normalized_to_asyncpg():
    settings = _settings(DATABASE_URL="postgresql://user:pass@host:5432/behaviordb")
    assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@host:5432/behaviordb"


def test_supabase_session_pooler_url_is_preserved():
    url = (
        "postgresql+asyncpg://postgres.ref:pass@"
        "aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )
    settings = _settings(DATABASE_URL=url)
    assert settings.DATABASE_URL == url


def test_prepared_statement_cache_toggle_defaults_off():
    assert _settings().DATABASE_DISABLE_PREPARED_STATEMENTS is False


def test_prepared_statement_cache_can_be_disabled_for_transaction_pooler():
    settings = _settings(DATABASE_DISABLE_PREPARED_STATEMENTS=True)
    assert settings.DATABASE_DISABLE_PREPARED_STATEMENTS is True


def test_helper_model_split_is_unchanged():
    settings = _settings()
    assert settings.NVIDIA_MODEL_FAST == "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    assert settings.NVIDIA_MODEL_STRONG == "nvidia/nemotron-3-ultra-550b-a55b"
    assert [
        settings.NVIDIA_MODEL_FAST,
        settings.NVIDIA_MODEL_FAST,
        settings.NVIDIA_MODEL_STRONG,
    ] == [
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        "nvidia/nemotron-3-ultra-550b-a55b",
    ]
