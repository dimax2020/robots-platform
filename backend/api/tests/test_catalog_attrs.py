from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.config import Settings
from api.db.models import Product
from api.deps import get_db
from api.routers import catalog
from api.schemas.catalog import CatalogAttrs
from api.services import catalog as svc

REPO_DATA = Path(__file__).resolve().parents[3] / "data"


@pytest.fixture
def db() -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.first.return_value = None
    result.all.return_value = []
    session.execute.return_value = result
    session.scalar.return_value = None
    session.scalars.return_value.all.return_value = []
    return session


@pytest.fixture
def client(db: MagicMock, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(svc, "get_settings", lambda: Settings(data_dir=REPO_DATA))

    app = FastAPI()
    app.include_router(catalog.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _product(*, attrs: dict | None = None) -> Product:
    return Product(
        id=uuid4(),
        solution_type_id=1,
        slug="demo",
        name="Demo",
        manufacturer="Acme",
        availability="operation",
        attrs=attrs if attrs is not None else {},
        valid_from=1,
    )


def test_attrs_response_shape(client: TestClient, db: MagicMock) -> None:
    filled = _product(
        attrs={
            "payload_kg": {
                "status": "known",
                "value": 12,
                "unit": "кг",
                "source_id": 17,
                "quote": "до 12 кг",
            }
        }
    )
    empty = _product(attrs={})
    empty.slug = "empty"
    db.scalars.return_value.all.return_value = [filled, empty]
    db.scalar.return_value = 3

    res = client.get("/api/v1/catalog/attrs")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["catalog_version_id"] == 3
    assert set(body["attrs"]) == {str(filled.id), str(empty.id)}
    assert body["attrs"][str(filled.id)]["payload_kg"]["status"] == "known"
    assert body["attrs"][str(filled.id)]["payload_kg"]["value"] == 12
    assert body["attrs"][str(empty.id)] == {}
    CatalogAttrs.model_validate(body)


def test_attrs_empty_product_dict(client: TestClient, db: MagicMock) -> None:
    product = _product(attrs={})
    db.scalars.return_value.all.return_value = [product]
    db.scalar.return_value = 1

    res = client.get("/api/v1/catalog/attrs")
    assert res.status_code == 200
    assert res.json()["attrs"][str(product.id)] == {}


def test_attrs_includes_unknown(client: TestClient, db: MagicMock) -> None:
    product = _product(
        attrs={"charge_time_h": {"status": "unknown", "value": None}}
    )
    db.scalars.return_value.all.return_value = [product]
    db.scalar.return_value = 2

    res = client.get("/api/v1/catalog/attrs")
    assert res.status_code == 200
    value = res.json()["attrs"][str(product.id)]["charge_time_h"]
    assert value["status"] == "unknown"
    assert value["value"] is None


def test_compare_spec_twelve_params_with_rationale(client: TestClient) -> None:
    res = client.get("/api/v1/catalog/compare-spec")
    assert res.status_code == 200, res.text
    params = res.json()
    assert len(params) == 12
    keys = [p["key"] for p in params]
    assert keys == [
        "count",
        "score",
        "reliability",
        "data_completeness",
        "payload_kg",
        "speed_loaded_ms",
        "throughput",
        "work_time_h",
        "charge_time_h",
        "min_aisle_width_m",
        "price_rub",
        "park_price_rub",
    ]
    for param in params:
        assert param["rationale"].strip()
        assert param["better"] in {"max", "min", "none"}
        assert set(param) >= {
            "key",
            "label",
            "unit",
            "group",
            "origin",
            "better",
            "rationale",
        }
    assert "_note" not in str(params)


def test_compare_spec_broken_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "compare_spec.json"
    bad.write_text(
        '{"params": [{"key": "count", "label": "x", "group": "operational",'
        ' "origin": "engine", "better": "min", "rationale": ""}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(svc, "get_settings", lambda: Settings(data_dir=tmp_path))

    res = client.get("/api/v1/catalog/compare-spec")
    assert res.status_code == 500
    assert "rationale" in res.json()["detail"].lower()


def test_compare_spec_missing_file(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(svc, "get_settings", lambda: Settings(data_dir=tmp_path))
    res = client.get("/api/v1/catalog/compare-spec")
    assert res.status_code == 500
    assert "не найден" in res.json()["detail"].lower()
