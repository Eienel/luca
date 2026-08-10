# Two-minute judge demo

A reproducible narrated draft can be generated on Windows with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_demo_video.ps1
```

The script uses the verified screenshots in `docs/screenshots/` and writes
`demo/changesafe-demo.mp4`. Use the live walkthrough below for the strongest
submission recording; the generated draft is a ready fallback.

## 0:00-0:15 - Pain

"Luca is an organizational change-intelligence platform, and ChangeSafe is its
schema-change product. A producer's tests can be green while a column rename
silently breaks Finance, Growth, Support, and an ML model. DataHub knows those
organizational consumers; ChangeSafe turns that context into a reviewable repair."

## 0:15-0:35 - Prove the break

Run:

```bash
python scripts/run_local_proof.py
```

Point to `no such column: customer_id`. This is a real SQLite execution over
four dbt-shaped downstream models, not a slide or an LLM claim.

## 0:35-1:15 - DataHub context and impact

Open the UI, show the 100/100 convergence score, six graph consumers, inferred
column roles, and five known consumers affected by the rename. Say explicitly:

"In live mode, these entities, schemas, query examples, and column-level paths
come through DataHub MCP. Missing metadata remains an unknown-coverage warning."

## 1:15-1:40 - Action

Show the compatibility SQL and regression SQL. Click **Generate review package**.
Explain that the package contains code, a test, an owner-facing migration note,
and machine-readable impact evidence.

## 1:40-1:55 - Governed change

Run `scripts/apply_change_package.py` against the prepared fixture repository and
show the new `changesafe/...` branch and commit. Click **Approve & record** to
show the durable decision path back to DataHub.

## 1:55-2:00 - Close

"DataHub tells you what will break. ChangeSafe gives your team the reviewed code
to stop it from breaking."

## Claims to avoid

- Do not call the local MCP contract server a live DataHub deployment.
- Do not claim complete coverage when lineage or query history is missing.
- Do not claim autonomous merging; push and PR creation stay human-controlled.
