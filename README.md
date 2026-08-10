# ConsumerGraph

**ChangeSafe uses DataHub's organizational metadata graph to find every known consumer of a proposed schema change, generate a tested compatibility migration, package it for Git review, and record the decision back in DataHub.**

ConsumerGraph is the future suite. ChangeSafe is the focused hackathon product.

![ChangeSafe impact analysis and generated migration](docs/screenshots/02-impact-and-migration.jpg)

The hackathon MVP combines two workflows:

- **ConsumerSpec** infers a dependency contract from lineage, queries, usage, ownership, and cross-domain consumption.
- **ChangeSafe** tests a proposed schema change against that contract, generates compatibility SQL and regression tests, and writes the approved decision back to DataHub.

## Why it exists

Repository tests know whether producer code works. They usually do not know that Finance, Marketing, Support, and an ML model all depend on the same column. DataHub contains that organizational dependency graph; ConsumerGraph converts it into actionable change protection.

## Current vertical slice

1. Select a shared dataset.
2. Calculate its cross-team and cross-domain convergence score.
3. Inspect inferred column dependencies and their evidence.
4. Propose a rename, removal, or type change.
5. See known affected consumers and explicit unknown coverage.
6. Generate compatibility SQL and regression tests.
7. Generate a four-file review package and apply it as a real Git branch and commit.
8. Approve the decision and persist it locally or as a DataHub Document.

The analysis engine is deterministic. A local LLM may later explain results, but it is not allowed to decide whether a change is safe.

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open <http://localhost:8000>.

The default `CONSUMERGRAPH_CATALOG_MODE=demo` requires no DataHub instance or paid API.

## DataHub MCP mode

ChangeSafe uses the official read tools `get_entities`, `list_schema_fields`,
`get_lineage`, and `get_dataset_queries`. It uses `save_document` for durable
write-back when mutations are enabled.

```bash
CONSUMERGRAPH_CATALOG_MODE=mcp
CONSUMERGRAPH_MODE=mcp
DATAHUB_MCP_URL=https://your-tenant.acryl.io/integrations/ai/mcp/
DATAHUB_MCP_TOKEN=<service-account-token>
DATAHUB_SOURCE_URN=urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.customer_360,PROD)
```

MCP mode fails closed when configuration or the server is unavailable; it never
silently substitutes the demo graph. The official public demo currently returns
`401 Unauthorized` for GMS and MCP routes, so it cannot be used as an anonymous
integration target.

Run the read-only live acceptance probe before using a tenant in the UI:

```bash
python scripts/verify_live_datahub.py --column customer_id --new-name buyer_id
```

The probe reads credentials only from the environment, never prints the token,
and performs no mutation.

### Verified live OSS proof

The [`live-datahub` workflow](https://github.com/Eienel/consumergraph/actions/runs/31136996090)
completed successfully against DataHub OSS 1.7.0 and the official MCP server. It
loaded four schema fields and ten downstream consumers for `logging_events`,
traced `event_data` to `fct_users_created.user_name`, returned
`migration_required`, generated the migration package, and created a real DataHub
Document through `save_document`. It then read that document back successfully
on the first attempt. The compact captured result is in
[`examples/live-datahub-proof.json`](examples/live-datahub-proof.json).

The ready-to-upload 1:51 narrated demo is
[`demo/changesafe-demo.mp4`](demo/changesafe-demo.mp4).

## DataHub write-back

Install the DataHub SDK extra:

```bash
pip install -e ".[datahub,dev]"
```

Configure:

```bash
CONSUMERGRAPH_MODE=datahub
DATAHUB_GMS_URL=http://localhost:8080
DATAHUB_GMS_TOKEN=<personal-access-token>
```

When a migration is approved, ConsumerGraph uses `DataHubClient` and `Document.create_document(...)` to publish the decision, generated SQL, tests, affected owners, confidence, and coverage warning. The document is linked to the source dataset when its URN is available.

For a rich local catalog, load the official showcase datapack:

```bash
datahub datapack load showcase-ecommerce
```

## Git review workflow

The UI's **Generate review package** action creates compatibility SQL, regression
SQL, `MIGRATION.md`, and `impact.json`. After review, apply it to a clean target
repository:

```bash
python scripts/apply_change_package.py <package-directory> <target-repository>
```

ChangeSafe creates a `changesafe/...` branch and a real commit, refuses dirty
repositories, and refuses to overwrite existing files. Pushing and opening a PR
remain explicit human actions.

## Tests

```bash
pytest
python scripts/run_local_proof.py
```

The local proof uses a dbt-shaped project and Python's built-in SQLite engine, so it
needs no warehouse, paid API, or Docker. It first proves that renaming
`customer_id` to `buyer_id` breaks four downstream models, then runs ConsumerGraph,
applies its generated compatibility view, and proves every model works again.

The fixture is intentionally small enough to audit line by line. The full local
Quickstart is not run on this laptop because DataHub recommends allocating at
least 8 GB to Docker; the live GitHub workflow runs it on a 16 GB hosted runner.

The repository separately contract-tests the full MCP initialize/session/tool-call
sequence against a lightweight local server, while the live workflow proves
interoperability with actual DataHub OSS and the official MCP implementation.

## Safety model

- Observed usage is evidence, not automatically binding policy.
- Missing lineage is reported as unknown coverage.
- Generated migrations require human approval.
- Destructive changes with known consumers are blocked by default.
- No raw business-customer records are required; the MVP analyzes organizational metadata consumers.

## Roadmap

The same dependency intelligence can later power IncidentGraph, TimeFence,
TrainServe, and, through a warehouse execution layer, business-customer journey
convergence.

See [docs/VALIDATION.md](docs/VALIDATION.md) for the evidence, limits, and local
break/repair proof behind the product claim.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the bounded build and
[examples/change-package](examples/change-package) for a judge-readable output.


Apache License 2.0.
