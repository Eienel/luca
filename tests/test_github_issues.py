import json
from datetime import UTC, datetime

from app.campaigns import create_campaign, dispatch_github_issue
from app.github_issues import GitHubIssueAdapter
from app.models import CampaignCreateRequest
from tests.test_campaigns import _decision


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeGitHub:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        if request.method == "GET":
            return FakeResponse(self.existing)
        return FakeResponse({"number": 42, "html_url": "https://github.com/acme/data/issues/42"})


def test_adapter_creates_issue_without_exposing_token():
    fake = FakeGitHub()
    adapter = GitHubIssueAdapter("acme/data", "secret-token", labels=["changesafe"], opener=fake)
    receipt = adapter.ensure_issue(title="Migration", body="Evidence", marker="marker-1")

    assert receipt.number == 42
    assert receipt.created is True
    assert [request.method for request, _ in fake.requests] == ["GET", "POST"]
    post = fake.requests[1][0]
    assert json.loads(post.data)["labels"] == ["changesafe"]
    assert post.headers["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in post.full_url


def test_adapter_reuses_existing_marker_instead_of_creating_duplicate():
    fake = FakeGitHub(
        [{"number": 7, "html_url": "https://github.com/acme/data/issues/7", "body": "marker-1"}]
    )
    adapter = GitHubIssueAdapter("acme/data", "token", opener=fake)
    receipt = adapter.ensure_issue(title="Migration", body="Evidence", marker="marker-1")

    assert receipt.number == 7
    assert receipt.created is False
    assert [request.method for request, _ in fake.requests] == ["GET"]


def test_campaign_dispatch_is_durable_and_idempotent(tmp_path):
    decision_id = _decision(tmp_path)
    campaign = create_campaign(
        CampaignCreateRequest(decision_id=decision_id, reviewed_by="reviewer", review_approved=True),
        tmp_path,
        now=datetime(2026, 8, 9, 12, tzinfo=UTC),
    )
    task_id = campaign["tasks"][0]["id"]
    fake = FakeGitHub()
    adapter = GitHubIssueAdapter("acme/data", "token", opener=fake)

    dispatched = dispatch_github_issue(
        campaign["id"],
        task_id,
        "reviewer",
        tmp_path,
        adapter,
        now=datetime(2026, 8, 9, 13, tzinfo=UTC),
    )
    task = next(item for item in dispatched["tasks"] if item["id"] == task_id)
    assert task["delivery_status"] == "sent"
    assert task["delivery_receipt"]["issue_number"] == 42
    assert task["delivery_receipt"]["created"] is True
    assert "Coverage warning" in fake.requests[1][0].data.decode("utf-8")

    retried = dispatch_github_issue(campaign["id"], task_id, "reviewer", tmp_path, adapter)
    assert retried == dispatched
    assert len(fake.requests) == 2
