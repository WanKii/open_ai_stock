"""Test configuration — uses isolated temp databases for every test session."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

# Redirect data to a temporary directory BEFORE any app module is imported.
_tmp_dir = tempfile.mkdtemp(prefix="stocktest_")
os.environ.setdefault("STOCK_ANALYSIS_DATA_DIR", _tmp_dir)

# Patch config paths so no real user data is touched.
import app.core.config as _cfg  # noqa: E402

_cfg.DATA_DIR = Path(_tmp_dir)
_cfg.CONFIG_DIR = Path(_tmp_dir) / "config"
_cfg.SETTINGS_PATH = _cfg.CONFIG_DIR / "local_settings.toml"
_cfg.SQLITE_PATH = _cfg.DATA_DIR / "test_app.db"
_cfg.DUCKDB_PATH = _cfg.DATA_DIR / "test_market.duckdb"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_app():
    """Run startup hooks once for the whole test session."""
    from app.core.database import init_db
    from app.core.market_store import init_market_store

    _cfg.ensure_project_dirs()
    init_db()
    init_market_store()
    _cfg.load_settings()
    yield
    # Cleanup temp dir
    shutil.rmtree(_tmp_dir, ignore_errors=True)


@pytest.fixture()
def client():
    """Synchronous TestClient from FastAPI."""
    return TestClient(fastapi_app)
