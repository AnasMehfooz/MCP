"""The migrations and the models must describe the same database.

Other tests build their tables straight from the models (fast). These run the real
migrations in an empty schema, so a model change without a migration fails here.
"""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Connection, inspect

from store.config import PROJECT_ROOT
from store.metadata import metadata


def _alembic(connection: Connection) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.attributes["connection"] = connection  # migrations/env.py uses it instead of the app database
    return config


def test_upgrade_builds_exactly_what_the_models_describe(engine):
    with engine.begin() as conn:
        command.upgrade(_alembic(conn), "head")

    with engine.connect() as conn:
        assert set(inspect(conn).get_table_names()) == set(metadata.tables) | {"alembic_version"}
        # What `alembic revision --autogenerate` would still want to change: nothing.
        assert compare_metadata(MigrationContext.configure(conn), metadata) == []


def test_downgrade_removes_every_table(engine):
    with engine.begin() as conn:
        command.upgrade(_alembic(conn), "head")
        command.downgrade(_alembic(conn), "base")

    with engine.connect() as conn:
        assert inspect(conn).get_table_names() == ["alembic_version"]
