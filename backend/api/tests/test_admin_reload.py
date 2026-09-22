from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_db
from api.routers import admin
from api.services.catalog import reload_app_catalog
from engine.models import Catalog


def test_reload_app_catalog_writes_state() -> None:
    app = MagicMock()
    db = MagicMock()
    catalog = Catalog(version_id=3)
    with patch("api.services.catalog.load_engine_catalog", return_value=catalog):
        result = reload_app_catalog(app, db)
    assert result is catalog
    assert app.state.catalog is catalog


def test_admin_reload_endpoint() -> None:
    db = MagicMock()
    app = FastAPI()
    app.include_router(admin.router, prefix="/api/v1")
    app.state.catalog = Catalog(version_id=0)
    app.dependency_overrides[get_db] = lambda: db

    fresh = Catalog(version_id=4)
    with patch("api.routers.admin.svc.reload_app_catalog", return_value=fresh) as reload:
        client = TestClient(app)
        res = client.post("/api/v1/admin/catalog/reload")
    assert res.status_code == 200
    assert res.json() == {"catalog_version_id": 4, "products": 0}
    reload.assert_called_once()


def test_patch_attrs_reloads_snapshot() -> None:
    from datetime import date
    from uuid import uuid4

    from api.db.models import Product, Source
    from api.schemas.catalog import ProductDetail, RefOut

    product_id = uuid4()
    product = Product(
        id=product_id,
        solution_type_id=1,
        slug="h1500",
        name="H1500",
        manufacturer="Rona",
        availability="operation",
        attrs={},
        valid_from=1,
    )
    source = Source(
        id=1,
        kind="vendor",
        captured_at=date(2026, 1, 1),
        publisher="Rona",
    )
    db = MagicMock()
    db.scalar.side_effect = [product, source]
    db.scalars.return_value.all.return_value = ["payload_kg"]

    detail = ProductDetail(
        id=product_id,
        slug="h1500",
        name="H1500",
        manufacturer="Rona",
        availability="operation",
        auto_match=True,
        solution_type=RefOut(code="amr", name="AMR"),
        family="flow_cycle",
        completeness_filled=0,
        completeness_total=0,
    )

    app = FastAPI()
    app.include_router(admin.router, prefix="/api/v1")
    app.state.catalog = Catalog(version_id=1)
    app.dependency_overrides[get_db] = lambda: db

    with (
        patch("api.routers.admin.svc.reload_app_catalog") as reload,
        patch("api.routers.admin.svc.product_detail", return_value=detail),
    ):
        client = TestClient(app)
        res = client.patch(
            f"/api/v1/admin/products/{product_id}/attrs",
            json={"values": {"payload_kg": {"status": "known", "value": 1500}}},
        )
    assert res.status_code == 200, res.text
    reload.assert_called_once()
