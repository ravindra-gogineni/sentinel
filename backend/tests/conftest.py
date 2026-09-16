"""Shared pytest fixtures for the SENTINEL backend test suite."""
import pytest

from app.config import get_settings
from app.risk import incidents as incidents_module


@pytest.fixture(autouse=True)
def isolated_incident_db(monkeypatch, tmp_path):
    """
    Every test runs against its OWN temp SQLite file:
      - SENTINEL_DB_PATH points into the pytest tmp dir (never the dev sentinel.db)
      - the cached IncidentService singleton is dropped so engine-driven tests
        pick up the temp path fresh.
    """
    incidents_module._service = None
    monkeypatch.setenv("SENTINEL_DB_PATH", str(tmp_path / "sentinel_test.db"))
    get_settings.cache_clear()
    yield
    incidents_module._service = None
    get_settings.cache_clear()