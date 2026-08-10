from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .artifacts import write_change_package
from .campaigns import create_campaign, dispatch_github_issue, get_campaign, list_campaigns, update_campaign_task
from .catalog import CatalogRepository
from .datahub_mcp import DataHubMcpCatalog
from .engine import ConsumerGraphEngine
from .github_issues import GitHubIssueAdapter
from .mcp_client import McpClient
from .models import (
    CampaignCreateRequest,
    CampaignGitHubDispatchRequest,
    CampaignTaskUpdate,
    ChangeRequest,
    WritebackRequest,
)
from .writeback import save_writeback

ROOT = Path(__file__).resolve().parents[1]


def _runtime_dir() -> Path:
    configured = os.getenv("CONSUMERGRAPH_RUNTIME_DIR")
    if configured:
        return Path(configured)
    if os.getenv("VERCEL"):
        return Path("/tmp/consumergraph-runtime")
    return ROOT / "runtime"


RUNTIME_DIR = _runtime_dir()


def _load_catalog() -> tuple[CatalogRepository, str, DataHubMcpCatalog | None]:
    mode = os.getenv("CONSUMERGRAPH_CATALOG_MODE", "demo").lower()
    if mode == "demo":
        return CatalogRepository(ROOT / "data" / "demo_graph.json"), mode, None
    if mode != "mcp":
        raise RuntimeError("CONSUMERGRAPH_CATALOG_MODE must be 'demo' or 'mcp'")
    url = os.environ.get("DATAHUB_MCP_URL")
    urn = os.environ.get("DATAHUB_SOURCE_URN")
    if not url or not urn:
        raise RuntimeError("DATAHUB_MCP_URL and DATAHUB_SOURCE_URN are required in MCP catalog mode")
    client = McpClient(url, token=os.environ.get("DATAHUB_MCP_TOKEN"))
    adapter = DataHubMcpCatalog(client)
    return adapter.load(urn), mode, adapter


catalog, catalog_mode, mcp_adapter = _load_catalog()
engine = ConsumerGraphEngine(catalog)

app = FastAPI(title="ChangeSafe by ConsumerGraph", version="0.2.0")
app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "app" / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "catalog_mode": catalog_mode, "engine": "deterministic"}


@app.get("/api/assets")
def assets():
    return [asset.model_dump(exclude={"queries"}) for asset in catalog.catalog.assets]


@app.get("/api/assets/{asset_id}/convergence")
def convergence(asset_id: str):
    try:
        return engine.convergence(asset_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/assets/{asset_id}/contract")
def contract(asset_id: str):
    try:
        return engine.infer_contract(asset_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/change/analyze")
def analyze(request: ChangeRequest):
    try:
        if mcp_adapter:
            mcp_adapter.enrich_column(catalog, request.asset_id, request.column)
        return engine.analyze_change(request)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/change/writeback")
def writeback(request: WritebackRequest):
    try:
        return save_writeback(request.analysis, RUNTIME_DIR)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(500, str(exc)) from exc


@app.post("/api/change/package")
def package_change(request: ChangeRequest):
    try:
        if mcp_adapter:
            mcp_adapter.enrich_column(catalog, request.asset_id, request.column)
        analysis = engine.analyze_change(request)
        return write_change_package(analysis, RUNTIME_DIR / "generated")
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/change/campaigns")
def campaign_create(request: CampaignCreateRequest):
    try:
        return create_campaign(request, ROOT / "runtime")
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/change/campaigns")
def campaign_list():
    try:
        return list_campaigns(ROOT / "runtime")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/change/campaigns/{campaign_id}")
def campaign_get(campaign_id: str):
    try:
        return get_campaign(campaign_id, ROOT / "runtime")
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/change/campaigns/{campaign_id}/tasks/{task_id}")
def campaign_task_update(campaign_id: str, task_id: str, request: CampaignTaskUpdate):
    try:
        return update_campaign_task(campaign_id, task_id, request, ROOT / "runtime")
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/api/change/campaigns/{campaign_id}/tasks/{task_id}/dispatch/github")
def campaign_github_dispatch(campaign_id: str, task_id: str, request: CampaignGitHubDispatchRequest):
    try:
        adapter = GitHubIssueAdapter.from_env()
        return dispatch_github_issue(campaign_id, task_id, request.actor, ROOT / "runtime", adapter)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
