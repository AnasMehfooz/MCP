"""Settings come from the environment (or .env) and fail at startup when they are wrong."""

import uuid

import pytest
from pydantic import ValidationError

from store.config import Settings

ENV_VARS = ("STORE_DATABASE_URL", "STORE_ID", "STORE_LOW_STOCK_THRESHOLD", "STRIPE_WEBHOOK_SECRET")


@pytest.fixture
def load(monkeypatch):
    """Build Settings from exactly the given variables: clean environment, no .env file."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    def _load(**variables: str) -> Settings:
        for name, value in variables.items():
            monkeypatch.setenv(name, value)
        return Settings(_env_file=None)

    return _load


def test_defaults_match_docker_compose(load):
    s = load()
    assert s.database_url == "postgresql+psycopg://store:store@localhost:5432/store"
    assert (s.store_id, s.low_stock_threshold, s.stripe_webhook_secret) == (None, 5, None)


def test_environment_overrides_defaults(load):
    store_id = uuid.uuid4()
    s = load(STORE_ID=str(store_id), STORE_LOW_STOCK_THRESHOLD="2", STRIPE_WEBHOOK_SECRET="whsec_test")
    assert (s.store_id, s.low_stock_threshold) == (store_id, 2)
    assert s.stripe_webhook_secret.get_secret_value() == "whsec_test"
    assert "whsec_test" not in repr(s)  # secrets stay out of logs and tracebacks


def test_empty_values_count_as_unset(load):
    assert load(STORE_ID="").store_id is None


@pytest.mark.parametrize(
    ("given", "used"),
    [
        ("postgresql://u:p@db:5432/x", "postgresql+psycopg://u:p@db:5432/x"),
        ("postgres://u:p@db/x", "postgresql+psycopg://u:p@db/x"),
        ("postgresql+psycopg://u:p@db/x", "postgresql+psycopg://u:p@db/x"),
    ],
)
def test_postgres_urls_without_a_driver_get_the_installed_one(load, given, used):
    assert load(STORE_DATABASE_URL=given).database_url == used


@pytest.mark.parametrize(
    "variables",
    [{"STORE_DATABASE_URL": "sqlite:///store.db"}, {"STORE_ID": "not-a-uuid"}, {"STORE_LOW_STOCK_THRESHOLD": "-1"}],
)
def test_bad_values_fail_at_startup(load, variables):
    with pytest.raises(ValidationError):
        load(**variables)
