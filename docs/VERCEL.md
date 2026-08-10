# Vercel deployment

The deployment is live at <https://useluca.vercel.app>.

ChangeSafe remains one FastAPI application. `app/index.py` is the Vercel-supported
ASGI entrypoint and re-exports the same `app` used locally. No separate frontend
build or output directory is required.

## Connect the repository

1. Import `Eienel/luca` into Vercel.
2. Leave Framework Preset, Build Command, Output Directory, and Install Command at
   their automatically detected defaults.
3. Deploy the UI branch for preview, then switch the production branch to `main`
   after the pull request is merged.

The default catalog and write-back modes are `demo`, so the public preview needs
no secret and no paid API. Vercel's temporary writable directory is used for demo
packages and receipts because deployed function source is read-only. Those demo
files are ephemeral and are not a substitute for DataHub write-back.

## Optional DataHub configuration

Set these only when deploying against a private DataHub tenant:

```text
LUCA_CATALOG_MODE=mcp
LUCA_MODE=mcp
DATAHUB_MCP_URL=https://your-tenant.acryl.io/integrations/ai/mcp/
DATAHUB_MCP_TOKEN=<service-account-token>
DATAHUB_SOURCE_URN=<dataset-urn>
```

Never expose tokens in frontend JavaScript or commit them to the repository.

## Verification after deployment

- Open `/api/health` and confirm an `ok` response.
- Load `/` and confirm the catalog status becomes ready.
- Complete the `customer_360` -> `customer_id` -> `buyer_id` rename path.
- Generate the package and record the demo receipt.
- Confirm the interface never claims unknown consumers were covered or owners
  were notified.
