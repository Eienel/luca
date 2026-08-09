# Change Campaigns

Change Campaigns is the review-to-coordination extension for ChangeSafe. After a
human records an approved change decision, it converts every known affected
consumer into a deduplicated owner task and stores an auditable notification
outbox.

The current implementation is deliberately **outbox-only**. It creates truthful
message drafts and durable acknowledgement events; it does not send email, Slack,
GitHub messages, or voice calls.

## Why this is a mechanism, not a notification button

Each task stays linked to the DataHub-derived impact evidence that selected its
consumer and owner. The campaign records who approved the change, which consumers
are covered, what remains unknown, who acknowledged the work, and whether the
migration is blocked or complete.

The flow is:

**impact analysis -> human review -> recorded decision -> owner tasks -> future
delivery adapters -> acknowledgement/completion -> durable audit history**

## Safety properties in the current branch

- A campaign requires an existing recorded ChangeSafe decision.
- `review_approved` must be explicit and a reviewer identity is retained.
- One campaign is created per decision; retries return the same campaign and
  cannot duplicate future outreach.
- Consumers with the same owner are grouped into one task.
- Every draft says that no external notification has been sent.
- Status changes follow bounded transitions and retain actor, timestamp, and note.
- Completed tasks are terminal.
- Campaign and task identifiers are validated before filesystem access.
- Campaign writes use atomic replacement.
- AI is not used to select recipients, decide safety, or claim acknowledgement.

## API sequence

First analyze and record the reviewed decision using the existing endpoints:

```text
POST /api/change/analyze
POST /api/change/writeback
```

Create the outbox from the returned `document_id`:

```http
POST /api/change/campaigns
Content-Type: application/json

{
  "decision_id": "consumergraph-customer-360-customer-id-...",
  "reviewed_by": "reviewer@example.com",
  "review_approved": true,
  "due_at": "2026-08-10T12:00:00Z"
}
```

Read campaigns:

```text
GET /api/change/campaigns
GET /api/change/campaigns/{campaign_id}
```

Record an owner action:

```http
POST /api/change/campaigns/{campaign_id}/tasks/{task_id}
Content-Type: application/json

{
  "status": "acknowledged",
  "actor": "affected-owner@example.com",
  "note": "I own this migration"
}
```

Task actions are `acknowledged`, `blocked`, `completed`, and `reassigned`.
Reassignment also requires `new_owner`.

## Frontend integration boundary

The frontend may show a **Create coordination draft** action only after decision
write-back succeeds. The resulting state must say **draft** or **not sent**. It may
show owner tasks and allow manual acknowledgement, but it must not display channel
delivery, contact destinations, or sent status because no delivery adapter exists.

This branch does not modify `app/static/`, so it can be merged independently from
the collaborator's UI branch.

## Later delivery adapters

GitHub issues or pull-request comments are the best first real adapter because
they attach the request to code and produce a durable receipt. Slack and email can
follow. AI may draft evidence-linked explanations, but deterministic ownership and
human review remain authoritative.

AI voice calls should be considered only for opted-in, high-severity escalation
after ordinary channels fail. They require identity checks, explicit AI disclosure,
regional consent and recording controls, rate limits, opt-out, and audit logs.
