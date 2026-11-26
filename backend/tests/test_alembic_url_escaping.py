"""Alembic must accept real Supabase URLs with percent-encoded passwords."""
import pytest
from alembic.config import Config

from app.core.config import escape_alembic_url


def test_alembic_round_trips_a_percent_encoded_database_url(tmp_path):
    ini = tmp_path / "alembic.ini"
    ini.write_text(
        "[alembic]\nscript_location = .\nsqlalchemy.url = driver://placeholder\n",
        encoding="utf-8",
    )
    config = Config(str(ini))
    url = (
        "postgresql+asyncpg://postgres.ref:p%40ss%25word@"
        "aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    )

    config.set_main_option("sqlalchemy.url", escape_alembic_url(url))

    assert config.get_main_option("sqlalchemy.url") == url


def test_alembic_rejects_an_unescaped_percent_sign(tmp_path):
    ini = tmp_path / "alembic.ini"
    ini.write_text(
        "[alembic]\nscript_location = .\nsqlalchemy.url = driver://placeholder\n",
        encoding="utf-8",
    )
    config = Config(str(ini))

    with pytest.raises(ValueError):
        config.set_main_option(
            "sqlalchemy.url",
            "postgresql+asyncpg://postgres.ref:p%40ss@pooler:5432/postgres",
        )
