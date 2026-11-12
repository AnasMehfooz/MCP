from pathlib import Path

import pytest

from store import config


@pytest.fixture
def paths(tmp_path, monkeypatch):
    legacy = tmp_path / "project" / "data" / "store.db"
    default = tmp_path / "home" / ".ai-store" / "store.db"
    monkeypatch.setattr(config, "LEGACY_DB_PATH", legacy)
    monkeypatch.setattr(config, "DEFAULT_DB_PATH", default)
    return legacy, default


def test_env_override_wins(paths, tmp_path):
    legacy, _ = paths
    legacy.parent.mkdir(parents=True)
    legacy.touch()
    custom = tmp_path / "custom.db"
    assert config.resolve_db_path({"STORE_DB_PATH": str(custom)}) == custom.resolve()


def test_env_override_expands_user(paths):
    assert config.resolve_db_path({"STORE_DB_PATH": "~/shop.db"}) == (Path.home() / "shop.db").resolve()


def test_existing_project_db_is_kept(paths):
    legacy, _ = paths
    legacy.parent.mkdir(parents=True)
    legacy.touch()
    assert config.resolve_db_path({}) == legacy.resolve()


def test_defaults_to_home_dir_for_installed_copies(paths):
    _, default = paths
    assert config.resolve_db_path({}) == default.resolve()
