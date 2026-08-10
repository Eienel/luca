# Pain and mechanism validation

## Verdict

**The underlying pain is real; Luca's exact last-mile solution is
promising but not yet user-validated.**

The proven problem is that a producer can rename, remove, or retype a column
without knowing every downstream team, dashboard, pipeline, or model that will
break. The narrower Luca hypothesis is that impact reports are not
enough: teams also need an executable compatibility plan, regression tests, and
a durable record of the migration decision.

## External evidence

- DataHub introduced Dependency Impact Analysis specifically because schema
  migrations and breaking changes can damage downstream pipelines, reports, and
  ML models that the producer did not know existed:
  <https://datahub.com/blog/dependency-impact-analysis-data-validation-outcomes-and-more/>.
- DataHub's column-lineage guidance describes column renames silently breaking
  dashboards several hops downstream, and cites real producer/consumer
  coordination failures at Chime and safe-deprecation work at Uken Games:
  <https://datahub.com/blog/column-level-lineage-comes-to-datahub/>.
- dbt's official model-versioning documentation says downstream users need
  stable queries, that unplanned migrations are costlier than planned ones, and
  that renames/removals require real cross-team coordination:
  <https://docs.getdbt.com/docs/mesh/govern/model-versions>.
- A dbt Core issue shows the concrete failure mode: a removed column in an
  incremental model caused downstream query errors and blocked production use:
  <https://github.com/dbt-labs/dbt-core/issues/4144>.

These sources validate the category of pain. They do **not** prove that teams
want Luca's generated migration workflow, or that they would adopt it
instead of dbt versions, handwritten compatibility views, or existing internal
processes.

## Local mechanism proof

`scripts/run_local_proof.py` runs a reproducible, no-paid-API scenario against a
real SQL engine:

1. Build `customer_360` with `customer_id` and four downstream dbt-style models.
2. Rename the producer column to `buyer_id`.
3. Confirm the downstream build fails with `no such column: customer_id`.
4. Run Luca's deterministic impact analysis.
5. Confirm all four consumers are identified.
6. Apply the generated compatibility view.
7. Re-run every consumer and confirm they pass with zero alias mismatches.

Run it with:

```bash
python scripts/run_local_proof.py
```

This proves the mechanism on an auditable fixture. Docker Desktop is not run on
the test laptop because it has roughly 8 GB total RAM while DataHub recommends at
least 8 GB allocated to Docker. Quickstart interoperability is instead verified
on a 16 GB public GitHub-hosted runner, described below.

## Live DataHub OSS proof

[Workflow run 31136996090](https://github.com/Eienel/luca/actions/runs/31136996090)
completed against DataHub OSS 1.7.0. It started the real Quickstart stack,
ingested DataHub's official sample metadata, launched the official
`mcp-server-datahub` package over Streamable HTTP, and executed ChangeSafe.

Observed result:

- 4 schema fields loaded for `logging_events`.
- 10 downstream lineage consumers loaded.
- Column lineage connected `event_data` to `fct_users_created.user_name`.
- ChangeSafe returned `migration_required` and generated compatibility and
  regression SQL.
- MCP `save_document` returned success and created
  `urn:li:document:shared-f986d134-971d-4f4e-a7c6-ee38f89a1d0d`.
- MCP `get_entities` read that exact document URN back on the first attempt.
- The proof artifact and MCP diagnostics were retained by the workflow; a compact
  copy is committed at `examples/live-datahub-proof.json`.

## MCP and Git contract proof

`tests/test_mcp_contract.py` runs a local HTTP server and verifies the MCP
initialize notification, session header, and DataHub tool calls for entities,
schema, downstream lineage, and query history. The hydrated graph then finds all
four affected consumers. This is a protocol contract test, not a live DataHub
claim.

`tests/test_artifacts.py` generates the four-file review package, applies it to
a temporary clean Git repository, and verifies that ChangeSafe creates a named
branch and a real commit. The public hosted DataHub demo was also probed read-only
on August 7, 2026: the UI was public, while `/api/gms/config` and
`/api/gms/mcp` returned `401 Unauthorized`. No mutation was attempted.

## Cheapest remaining kill probes

1. Show five data engineers the generated impact plan and ask what they would
   still do manually before merging the change.
2. Import `showcase-ecommerce`, select one column with cross-tool lineage, and
   compare Luca's affected set with DataHub's native impact view.
3. Ask two teams to bring a recent breaking schema migration and reconstruct
   whether generated compatibility SQL would have reduced work or risk.

Kill or narrow the product if users say native DataHub impact analysis plus dbt
model versions already closes the workflow. Chase it if they repeatedly export
impact lists, contact owners manually, handwrite compatibility layers, or lack a
durable approval record.
