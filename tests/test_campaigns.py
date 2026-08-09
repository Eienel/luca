import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.campaigns import create_campaign, get_campaign, list_campaigns, update_campaign_task
from app.models import CampaignCreateRequest, CampaignTaskUpdate


def _decision(runtime_dir: Path) -> str:
    decision_id = "consumergraph-customer-360-customer-id-20260809t120000z"
    analysis = {
        "change": {"asset_id": "customer_360", "kind": "rename", "column": "customer_id", "new_name": "buyer_id"},
        "source": {"id": "customer_360", "name": "analytics.customer_360", "urn": "urn:li:dataset:test"},
        "severity": "critical",
        "unknown_coverage": "Consumers without captured lineage or query history may be missing.",
        "known_affected_consumers": [
            {
                "id": "finance_dashboard",
                "name": "Finance Dashboard",
                "type": "dashboard",
                "owner": "Finance Analytics",
                "domain": "Finance",
                "hops": 1,
                "criticality": 5,
            },
            {
                "id": "finance_model",
                "name": "finance.revenue",
                "type": "dataset",
                "owner": "Finance Analytics",
                "domain": "Finance",
                "hops": 2,
                "criticality": 4,
            },
            {
                "id": "growth_model",
                "name": "growth.segments",
                "type": "dataset",
                "owner": "Growth Data",
                "domain": "Marketing",
                "hops": 1,
                "criticality": 4,
            },
        ],
    }
    runtime_dir.mkdir(parents=True, exist_ok=True)
    (runtime_dir / f"{decision_id}.json").write_text(
        json.dumps({"id": decision_id, "analysis": analysis}),
        encoding="utf-8",
    )
    return decision_id


def test_campaign_requires_recorded_human_approval(tmp_path):
    decision_id = _decision(tmp_path)
    request = CampaignCreateRequest(
        decision_id=decision_id,
        reviewed_by="reviewer@example.com",
        review_approved=False,
    )
    with pytest.raises(PermissionError, match="human reviewer"):
        create_campaign(request, tmp_path)


def test_campaign_deduplicates_owners_and_creates_unsent_outbox(tmp_path):
    decision_id = _decision(tmp_path)
    request = CampaignCreateRequest(
        decision_id=decision_id,
        reviewed_by="reviewer@example.com",
        review_approved=True,
        due_at=datetime(2026, 8, 10, 12, tzinfo=UTC),
    )
    campaign = create_campaign(request, tmp_path, now=datetime(2026, 8, 9, 12, tzinfo=UTC))

    assert campaign["status"] == "draft"
    assert campaign["delivery_mode"] == "outbox_only"
    assert campaign["consumer_count"] == 3
    assert campaign["task_count"] == 2
    assert all(task["delivery_status"] == "not_sent" for task in campaign["tasks"])
    finance = next(task for task in campaign["tasks"] if task["owner"] == "Finance Analytics")
    assert finance["consumer_ids"] == ["finance_dashboard", "finance_model"]
    assert "No external notification has been sent" in finance["events"][0]["note"]
    assert get_campaign(campaign["id"], tmp_path) == campaign
    assert [item["id"] for item in list_campaigns(tmp_path)] == [campaign["id"]]
    retried = create_campaign(request, tmp_path, now=datetime(2026, 8, 9, 13, tzinfo=UTC))
    assert retried == campaign
    assert len(list_campaigns(tmp_path)) == 1


def test_campaign_task_transitions_are_durable_and_audited(tmp_path):
    decision_id = _decision(tmp_path)
    campaign = create_campaign(
        CampaignCreateRequest(decision_id=decision_id, reviewed_by="reviewer", review_approved=True),
        tmp_path,
        now=datetime(2026, 8, 9, 12, tzinfo=UTC),
    )
    task_id = campaign["tasks"][0]["id"]
    acknowledged = update_campaign_task(
        campaign["id"],
        task_id,
        CampaignTaskUpdate(status="acknowledged", actor="owner", note="Migration accepted"),
        tmp_path,
        now=datetime(2026, 8, 9, 13, tzinfo=UTC),
    )
    assert acknowledged["status"] == "in_progress"
    completed = update_campaign_task(
        campaign["id"],
        task_id,
        CampaignTaskUpdate(status="completed", actor="owner", note="PR merged"),
        tmp_path,
        now=datetime(2026, 8, 9, 14, tzinfo=UTC),
    )
    task = next(item for item in completed["tasks"] if item["id"] == task_id)
    assert task["status"] == "completed"
    assert task["delivery_status"] == "not_sent"
    assert task["events"][-1]["note"] == "PR merged"
    assert get_campaign(campaign["id"], tmp_path)["tasks"][0]["status"] == "completed"


def test_campaign_rejects_invalid_transition_and_missing_decision(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_campaign(
            CampaignCreateRequest(decision_id="missing-decision", reviewed_by="reviewer", review_approved=True),
            tmp_path,
        )

    decision_id = _decision(tmp_path)
    campaign = create_campaign(
        CampaignCreateRequest(decision_id=decision_id, reviewed_by="reviewer", review_approved=True),
        tmp_path,
    )
    with pytest.raises(ValueError, match="Cannot move task"):
        update_campaign_task(
            campaign["id"],
            campaign["tasks"][0]["id"],
            CampaignTaskUpdate(status="completed", actor="owner"),
            tmp_path,
        )
