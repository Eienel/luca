from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_http_vertical_slice():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "catalog_mode": "demo", "engine": "deterministic"}

    analysis = client.post(
        "/api/change/analyze",
        json={"asset_id": "customer_360", "kind": "rename", "column": "customer_id", "new_name": "buyer_id"},
    )
    assert analysis.status_code == 200
    assert len(analysis.json()["known_affected_consumers"]) >= 4

    package = client.post(
        "/api/change/package",
        json={"asset_id": "customer_360", "kind": "rename", "column": "customer_id", "new_name": "buyer_id"},
    )
    assert package.status_code == 200
    assert package.json()["review_status"] == "human_review_required"
    assert len(package.json()["files"]) == 4

    archive = client.post(
        "/api/change/package/download",
        json={"asset_id": "customer_360", "kind": "rename", "column": "customer_id", "new_name": "buyer_id"},
    )
    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(archive.content)) as downloaded:
        assert set(downloaded.namelist()) == set(package.json()["files"])
        assert "buyer_id AS customer_id" in downloaded.read("models/compatibility_view.sql").decode()

    migration = client.post(
        "/api/change/package/download?file=MIGRATION.md",
        json={"asset_id": "customer_360", "kind": "rename", "column": "customer_id", "new_name": "buyer_id"},
    )
    assert migration.status_code == 200
    assert "attachment; filename=\"MIGRATION.md\"" == migration.headers["content-disposition"]
    assert "Coverage warning" in migration.text


def test_http_rejects_incomplete_change_requests():
    rename = client.post(
        "/api/change/analyze",
        json={"asset_id": "customer_360", "kind": "rename", "column": "customer_id"},
    )
    type_change = client.post(
        "/api/change/analyze",
        json={"asset_id": "customer_360", "kind": "type_change", "column": "customer_id"},
    )
    assert rename.status_code == 422
    assert type_change.status_code == 422


def test_all_advertised_change_modes_generate_review_packages():
    requests = [
        {"asset_id": "customer_360", "kind": "rename", "column": "customer_id", "new_name": "buyer_id"},
        {"asset_id": "customer_360", "kind": "remove", "column": "customer_id"},
        {"asset_id": "customer_360", "kind": "type_change", "column": "customer_id", "new_type": "BIGINT"},
    ]
    for request in requests:
        response = client.post("/api/change/package", json=request)
        assert response.status_code == 200
        assert response.json()["review_status"] == "human_review_required"
        assert set(response.json()["files"]) == {
            "MIGRATION.md",
            "impact.json",
            "models/compatibility_view.sql",
            "tests/change_regression.sql",
        }
