from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import CampaignCreateRequest, CampaignTaskUpdate


_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,199}$")
_TRANSITIONS = {
    "draft": {"acknowledged", "blocked", "reassigned"},
    "acknowledged": {"blocked", "completed", "reassigned"},
    "blocked": {"acknowledged", "reassigned"},
    "reassigned": {"acknowledged", "blocked", "reassigned"},
    "completed": set(),
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def _timestamp(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _validate_id(value: str, label: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"Invalid {label}")
    return value


def _read_json(path: Path, missing_message: str) -> dict:
    if not path.is_file():
        raise FileNotFoundError(missing_message)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Unreadable campaign artifact: {path.name}") from exc


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _campaign_status(tasks: list[dict]) -> str:
    statuses = {task["status"] for task in tasks}
    if statuses == {"completed"}:
        return "completed"
    if "blocked" in statuses:
        return "blocked"
    if statuses - {"draft"}:
        return "in_progress"
    return "draft"


def _draft_message(analysis: dict, owner: str, consumers: list[dict], due_at: str | None) -> dict:
    change = analysis["change"]
    source = analysis["source"]
    consumer_names = ", ".join(item["name"] for item in consumers)
    deadline = f" Please respond by {due_at}." if due_at else ""
    return {
        "subject": f"Review required: {source['name']}.{change['column']} {change['kind']}",
        "body": (
            f"ChangeSafe found {len(consumers)} known consumer(s) owned by {owner} that may be affected: "
            f"{consumer_names}. The reviewed proposal changes {source['name']}.{change['column']} "
            f"using {change['kind']}. Please inspect the linked migration package, acknowledge ownership, "
            f"and report completion or a blocker.{deadline} Coverage warning: {analysis['unknown_coverage']}"
        ),
    }


def create_campaign(
    request: CampaignCreateRequest,
    runtime_dir: Path,
    *,
    now: datetime | None = None,
) -> dict:
    if not request.review_approved:
        raise PermissionError("A human reviewer must approve the recorded decision before campaign creation")
    decision_id = _validate_id(request.decision_id, "decision_id")
    decision = _read_json(runtime_dir / f"{decision_id}.json", f"Decision {decision_id!r} was not found")
    analysis = decision.get("analysis")
    if not isinstance(analysis, dict) or not isinstance(analysis.get("known_affected_consumers"), list):
        raise ValueError("The recorded decision has no usable impact analysis")
    affected = analysis["known_affected_consumers"]
    if not affected:
        raise ValueError("A campaign requires at least one known affected consumer")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for consumer in affected:
        owner = str(consumer.get("owner") or "Unassigned owner").strip()
        grouped[owner].append(consumer)

    created_at = _timestamp(now)
    campaign_id = _slug(f"campaign-{decision_id}")
    campaign_path = runtime_dir / "campaigns" / f"{campaign_id}.json"
    if campaign_path.is_file():
        return _read_json(campaign_path, f"Campaign {campaign_id!r} was not found")
    due_at = request.due_at.astimezone(UTC).isoformat() if request.due_at else None
    tasks = []
    for index, (owner, consumers) in enumerate(sorted(grouped.items()), start=1):
        tasks.append(
            {
                "id": f"task-{index}-{_slug(owner) or 'unassigned'}",
                "owner": owner,
                "consumer_ids": [item["id"] for item in consumers],
                "consumers": [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "type": item["type"],
                        "domain": item["domain"],
                        "hops": item["hops"],
                        "criticality": item["criticality"],
                    }
                    for item in consumers
                ],
                "status": "draft",
                "delivery_status": "not_sent",
                "contact_destination": None,
                "message": _draft_message(analysis, owner, consumers, due_at),
                "events": [
                    {
                        "type": "draft_created",
                        "actor": request.reviewed_by,
                        "at": created_at,
                        "note": "No external notification has been sent.",
                    }
                ],
            }
        )

    campaign = {
        "id": campaign_id,
        "decision_id": decision_id,
        "created_at": created_at,
        "reviewed_by": request.reviewed_by,
        "review_approved": True,
        "status": "draft",
        "delivery_mode": "outbox_only",
        "due_at": due_at,
        "source": analysis["source"],
        "change": analysis["change"],
        "severity": analysis["severity"],
        "unknown_coverage": analysis["unknown_coverage"],
        "task_count": len(tasks),
        "consumer_count": len(affected),
        "tasks": tasks,
        "events": [
            {
                "type": "campaign_created",
                "actor": request.reviewed_by,
                "at": created_at,
                "note": "Draft outbox created after recorded human approval; no messages sent.",
            }
        ],
    }
    _atomic_write(campaign_path, campaign)
    return campaign


def get_campaign(campaign_id: str, runtime_dir: Path) -> dict:
    campaign_id = _validate_id(campaign_id, "campaign_id")
    return _read_json(
        runtime_dir / "campaigns" / f"{campaign_id}.json",
        f"Campaign {campaign_id!r} was not found",
    )


def list_campaigns(runtime_dir: Path) -> list[dict]:
    campaign_dir = runtime_dir / "campaigns"
    if not campaign_dir.is_dir():
        return []
    campaigns = [_read_json(path, f"Campaign artifact {path.name!r} was not found") for path in campaign_dir.glob("*.json")]
    campaigns.sort(key=lambda item: item["created_at"], reverse=True)
    return campaigns


def update_campaign_task(
    campaign_id: str,
    task_id: str,
    request: CampaignTaskUpdate,
    runtime_dir: Path,
    *,
    now: datetime | None = None,
) -> dict:
    campaign = get_campaign(campaign_id, runtime_dir)
    task_id = _validate_id(task_id, "task_id")
    task = next((item for item in campaign["tasks"] if item["id"] == task_id), None)
    if task is None:
        raise FileNotFoundError(f"Task {task_id!r} was not found")
    if request.status not in _TRANSITIONS[task["status"]]:
        raise ValueError(f"Cannot move task from {task['status']} to {request.status}")
    if request.status == "reassigned" and not request.new_owner:
        raise ValueError("new_owner is required when reassigning a task")

    previous_status = task["status"]
    if request.new_owner:
        task["owner"] = request.new_owner
    task["status"] = request.status
    changed_at = _timestamp(now)
    task["events"].append(
        {
            "type": "status_changed",
            "actor": request.actor,
            "at": changed_at,
            "from": previous_status,
            "to": request.status,
            "note": request.note,
        }
    )
    campaign["status"] = _campaign_status(campaign["tasks"])
    campaign["events"].append(
        {
            "type": "task_status_changed",
            "task_id": task_id,
            "actor": request.actor,
            "at": changed_at,
            "from": previous_status,
            "to": request.status,
        }
    )
    _atomic_write(runtime_dir / "campaigns" / f"{campaign['id']}.json", campaign)
    return campaign
