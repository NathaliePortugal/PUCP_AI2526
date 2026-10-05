"""Fixture compartido: app real con base SQLite temporal y LLM reemplazable
via dependency_overrides. Comun a las pruebas de integracion y a los 6 casos."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vendebot.api.main import app
from vendebot.config import get_settings
from scripts.seed import TEST_CUSTOMERS, seed

PRODUCTS_CSV = Path("data/fixtures/products.csv")
C001_HEADERS = {"X-API-Key": "dev-key-c001"}
C002_HEADERS = {"X-API-Key": "dev-key-c002"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "integration.db"
    seed(db_path, products_csv=PRODUCTS_CSV, customers=TEST_CUSTOMERS)

    monkeypatch.setenv("SQLITE_PATH", str(db_path))
    monkeypatch.setenv("GEMINI_API_KEY", "unused-in-tests")
    get_settings.cache_clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    get_settings.cache_clear()
