import app.main as main_module
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


def test_reviewed_decision_can_create_and_track_an_unsent_campaign(tmp_path, monkeypatch):
    monkeypatch.setattr(main_module, "ROOT", tmp_path)
    analysis = client.post(
        "/api/change/analyze",
        json={"asset_id": "customer_360", "kind": "rename", "column": "customer_id", "new_name": "buyer_id"},
    ).json()
    decision = client.post("/api/change/writeback", json={"analysis": analysis})
    assert decision.status_code == 200

    campaign_response = client.post(
        "/api/change/campaigns",
        json={
            "decision_id": decision.json()["document_id"],
            "reviewed_by": "human-reviewer",
            "review_approved": True,
        },
    )
    assert campaign_response.status_code == 200
    campaign = campaign_response.json()
    assert campaign["delivery_mode"] == "outbox_only"
    assert campaign["consumer_count"] == len(analysis["known_affected_consumers"])
    assert all(task["delivery_status"] == "not_sent" for task in campaign["tasks"])

    task_id = campaign["tasks"][0]["id"]
    update = client.post(
        f"/api/change/campaigns/{campaign['id']}/tasks/{task_id}",
        json={"status": "acknowledged", "actor": "affected-owner", "note": "I own this migration"},
    )
    assert update.status_code == 200
    assert update.json()["status"] == "in_progress"
    fetched = client.get(f"/api/change/campaigns/{campaign['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["tasks"][0]["events"][-1]["actor"] == "affected-owner"
