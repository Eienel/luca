# UI/UX handoff for ChangeSafe

This brief is written for the designer/developer and their Claude Code session.
The product mechanism and backend already work. Your job is to make the workflow
immediately understandable, trustworthy, and memorable in a two-minute judge demo.

## The product in one sentence

ChangeSafe uses DataHub's organizational metadata graph to identify every known
consumer threatened by a schema change, generate tested migration code, package
it for Git review, and record the reviewed decision back in DataHub.

## The pain we are showing

A producer's repository tests can be green while renaming one column breaks a
Finance dashboard, Growth model, Support workflow, or ML feature table. The
missing context lives in lineage, query history, ownership, domains, and
column-level dependencies. DataHub contains that context; ChangeSafe converts it
into an observable developer action.

The interface must make this chain unmistakable:

**DataHub context -> organizational impact -> proposed change -> generated repair
-> human review -> durable DataHub decision**

## Primary user and moment

- User: data engineer, analytics engineer, or platform engineer.
- Trigger: they are about to rename, remove, or change the type of a shared column.
- Current workaround: inspect lineage, search queries, contact owners, handwrite a
  compatibility layer, create tests, and document the decision separately.
- Desired outcome: one reviewable impact and migration package before the change
  reaches production.

## What already works

Do not rebuild these mechanisms in the frontend:

- Deterministic convergence scoring and Luca dependency inference.
- Rename, removal, and type-change analysis.
- Known-consumer discovery with explicit unknown coverage.
- Compatibility SQL and executable regression-test generation.
- Four-file review-package generation.
- Real Git branch and commit application through the supplied script.
- Local and DataHub MCP decision write-back.
- Live DataHub OSS and official MCP integration proof.

The current frontend is a functional scaffold in `app/static/`. It may be fully
redesigned as long as the API contracts and truthful claims below remain intact.

## Required user journey

### 1. Establish DataHub connection and source

Show whether the app is using the deterministic demo or a connected DataHub MCP
catalog. Let the user select the shared data asset. DataHub should feel like the
source of organizational context, not a logo added after the fact.

### 2. Reveal convergence

Show why the dataset matters across the organization:

- convergence score and risk level;
- direct and total consumers;
- teams and domains reached;
- dashboards, models, and critical consumers;
- a readable map/list of downstream consumers and hop distance.

This is not customer-record analytics. “Consumer” means an organizational
consumer of data: a dashboard, dataset, workflow, feature table, or model.

### 3. Show the observed Luca dependency contract

For each source column, show its observed roles, consumer count, and confidence.
Make **Evidence, not policy** visible. Query usage and lineage are evidence of a
dependency, not proof that every dependency has been captured.

### 4. Pressure-test the change

The user chooses:

- Rename column: requires a new name.
- Remove column: no replacement value.
- Change type: requires a new type.

The result must make the verdict, severity, affected consumers, owners, and
coverage warning visible before generated code.

### 5. Turn evidence into action

Display compatibility SQL and the regression test legibly. The differentiator is
not merely finding impact; it is producing a tested, reviewable repair.

Provide two clear actions:

- **Generate review package** — returns four files for Git review.
- **Approve and record** — persists the decision locally or through DataHub MCP.

Neither action should imply autonomous merging. Human review is mandatory.

## Existing API contract

Keep these paths stable unless a coordinated backend change is discussed first.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Runtime status, catalog mode, deterministic engine status |
| GET | `/api/assets` | Assets available for selection |
| GET | `/api/assets/{asset_id}/convergence` | Score, reach metrics, and consumers |
| GET | `/api/assets/{asset_id}/contract` | Observed column dependencies and confidence |
| POST | `/api/change/analyze` | Impact verdict and generated migration/test |
| POST | `/api/change/package` | Generate the four-file review package |
| POST | `/api/change/writeback` | Record the reviewed decision |

Example change requests:

```json
{"asset_id":"customer_360","kind":"rename","column":"customer_id","new_name":"buyer_id"}
```

```json
{"asset_id":"customer_360","kind":"remove","column":"customer_id"}
```

```json
{"asset_id":"customer_360","kind":"type_change","column":"customer_id","new_type":"BIGINT"}
```

Inspect the actual responses in the browser network panel or `tests/test_api.py`.
Do not invent fields in the UI that the backend does not return.

## Required states

Design all of these, not only the happy-path screenshot:

- Initial loading.
- Demo mode and DataHub MCP connected mode.
- Asset selected and convergence loaded.
- Change form validation.
- Analysis in progress.
- Critical/high/moderate/low result.
- No known affected consumers, with unknown coverage still visible.
- Blocked removal or type change.
- Migration-required rename.
- Package-generation success and failure.
- Decision-writeback success and failure.
- Empty metadata or missing lineage/query evidence.
- Narrow/mobile layout and the primary desktop demo layout.

## Information hierarchy for the judge demo

The judge should understand the product without narration in this order:

1. **What could break?** — affected organizational consumers.
2. **Why do we believe that?** — DataHub lineage/query/ownership evidence.
3. **What should we do?** — generated compatibility and regression code.
4. **How is it governed?** — human review, Git package, DataHub write-back.
5. **What do we not know?** — explicit unknown-coverage warning.

Avoid spending the first screen on a generic marketing hero. Product evidence
should appear above the fold or after one obvious action.

## Visual direction

- Professional developer-tool interface, not a consumer analytics dashboard.
- Dense enough to communicate real evidence, but scannable in a two-minute demo.
- Strong distinction among source asset, affected consumers, generated action,
  and recorded decision.
- Use severity color with text/icons; never rely on color alone.
- SQL must remain readable at 1080p video resolution.
- Owner/team/domain labels should make the organizational graph tangible.
- Motion should clarify transitions, not delay the demo.
- Preserve keyboard access, visible focus, semantic labels, and useful contrast.

The existing dark/green visual language is optional. Keep it only if it helps the
workflow; do not treat the scaffold as a fixed design system.

## Truth and safety constraints

These phrases are product requirements:

- Say **every known consumer**, never “every consumer.”
- Always show that missing lineage or query history creates unknown coverage.
- Observed usage is evidence, not automatically binding policy.
- Generated migrations require human review.
- ChangeSafe creates a package/branch/commit; it does not autonomously merge.
- Do not show or require raw business-customer records.
- Do not add a paid API dependency or make an LLM responsible for the safety
  verdict. The analysis engine is deterministic.

## Technical boundaries

Preferred low-risk approach:

- Redesign `app/static/index.html`, `app/static/styles.css`, and
  `app/static/app.js`.
- Keep FastAPI serving the static application at `/`.
- Keep all existing API paths stable.
- Escape all catalog/API text before inserting HTML.
- Do not modify analysis, DataHub, Git, or write-back code merely to make mock UI
  states easier.

If introducing React, Vue, Svelte, or another build system, first ensure the
compiled static output can still be served by FastAPI with a one-command local
setup. Do not make Node a runtime requirement unless the team agrees.

## Local setup

```bash
git clone https://github.com/Eienel/luca.git
cd luca
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

Before opening a pull request:

```bash
pytest
node --check app/static/app.js
python scripts/run_local_proof.py
```

## Shared-repository workflow

After accepting the GitHub collaborator invitation:

```bash
git clone https://github.com/Eienel/luca.git
cd luca
git switch -c frontend/ui-ux-redesign
```

Commit only the UI work, push that branch, and open a pull request into `main`:

```bash
git add app/static docs/screenshots
git commit -m "Redesign ChangeSafe judge experience"
git push -u origin frontend/ui-ux-redesign
```

Do not both edit the same files on different branches without coordinating. Pull
the latest `main` before starting a new unit of work, keep changes small, and use
pull-request review rather than pushing directly to `main`.

## Acceptance checklist

- A new viewer can explain the problem and mechanism after one minute.
- The DataHub context -> impact -> repair -> governance chain is visible.
- Rename, remove, and type-change journeys work.
- Loading, empty, failure, blocked, and success states are designed.
- “Every known consumer” and unknown coverage remain visible.
- Compatibility SQL and regression SQL are readable in a 1080p recording.
- Package and write-back outcomes are visibly confirmed.
- Keyboard navigation and mobile layout work.
- No console errors or horizontal overflow at common desktop/mobile widths.
- Existing tests pass and no backend mechanism is replaced with mocked behavior.

## Paste this into Claude Code

```text
Read docs/UI_UX_HANDOFF.md completely, then inspect app/static, app/main.py,
tests/test_api.py, and the existing screenshots. Redesign the ChangeSafe frontend
for a two-minute DataHub hackathon judge demo. Preserve the existing API contracts,
deterministic backend, truthful coverage language, all three change modes, package
generation, and decision write-back. Implement loading, empty, failure, blocked,
and success states. Keep SQL readable at 1080p, use accessible semantic controls,
escape API-sourced content, and avoid paid APIs or autonomous-merge claims. Run
the listed tests and browser-check the complete journey before proposing the PR.
Do not change backend behavior merely to simplify the design; flag any needed API
change separately with a reason and migration plan.
```
