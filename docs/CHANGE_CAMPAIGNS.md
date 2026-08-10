# Change Campaigns: reviewed changes become coordinated work

## Product direction

ChangeSafe currently discovers every known organizational consumer threatened by
a schema change, creates a tested repair package, requires human review, and
records that decision. The next mechanism should close the coordination gap:

> After a human approves a migration plan, Change Campaigns turns the known impact
> graph into owner-specific, trackable migration work and records acknowledgements
> and completion evidence back into DataHub.

This is stronger than a generic notification feature. The useful primitive is a
durable campaign tied to graph evidence: who is affected, why they were selected,
what exact code or asset must change, who acknowledged it, and what remains unsafe.

## Why it belongs after human review

Lineage and query history are incomplete evidence, not authorization to contact
people or modify their repositories. The campaign must be created only after a
reviewer confirms the proposed change and recipient set. ChangeSafe must never
turn inferred ownership directly into autonomous outreach.

## Proposed workflow

1. ChangeSafe analyzes a proposed change and identifies known affected consumers.
2. A human reviews the impact, generated repair, owners, and coverage warning.
3. The reviewer approves a bounded change campaign.
4. The system creates one owner-specific task per affected consumer, deduplicated
   when the same owner controls several assets.
5. Configured adapters deliver the task through GitHub, Slack, or email.
6. Owners acknowledge, reject, reassign, or complete their task.
7. Campaign status and evidence are written back to the DataHub-linked decision.
8. The producer sees what is ready, blocked, unacknowledged, or still unknown
   before the destructive schema change is allowed to proceed.

## Minimum durable record

Each campaign should retain:

- change and source-asset identifiers;
- human reviewer and approval timestamp;
- affected consumer and the lineage/query evidence connecting it;
- resolved owner/team and delivery channel;
- requested migration action and relevant generated code;
- delivery, acknowledgement, reassignment, and completion status;
- timestamps, idempotency key, and an immutable event history; and
- the same explicit unknown-coverage warning shown during analysis.

## Role of AI

AI may draft an owner-specific explanation, summarize impact evidence, translate a
message, or suggest a patch. It must not decide that a change is safe, silently add
recipients, merge code, or claim that a person acknowledged work. Every AI-produced
message or patch remains reviewable and linked to the deterministic evidence that
caused it.

## Voice calls

AI-assisted calls are a possible later adapter, not an MVP requirement. Calls add
consent, identity, regional recording-law, opt-out, cost, impersonation, and abuse
risks. They should be considered only for opted-in, high-severity escalation after
ordinary channels fail, with an approved script, clear AI disclosure, rate limits,
audit logs, and a human escalation path.

## Deadline boundary

Do not implement external notification delivery for the current submission unless
the existing ChangeSafe flow is already complete and a reviewed backend contract,
test fixture, and durable receipt are added together. A frontend-only “sent” state
would be misleading.

For tomorrow's UI, the truthful endpoint is: show the known owners identified by
the existing analysis and make clear that coordination follows human review. The
current product already does the prize-relevant real work of producing a Git review
package and durable DataHub decision.

## Smallest post-submission probe

Before building several adapters, generate owner-specific task previews for five
real schema-change examples and ask affected engineers to perform the task from
the preview. Continue only if the evidence is sufficient to identify the correct
owner and action without manual reconstruction, and if engineers prefer the
campaign over their current coordination workflow.
