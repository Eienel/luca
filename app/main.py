from __future__ import annotations

import os
from pathlib import Path

from io import BytesIO

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .artifacts import change_package_archive, change_package_files, write_change_package
from .catalog import CatalogRepository
from .datahub_mcp import DataHubMcpCatalog
from .engine import LucaEngine
from .mcp_client import McpClient
from .models import ChangeRequest, WritebackRequest
from .writeback import save_writeback

ROOT = Path(__file__).resolve().parents[1]


def _runtime_dir() -> Path:
    configured = os.getenv("LUCA_RUNTIME_DIR") or os.getenv("CONSUMERGRAPH_RUNTIME_DIR")
    if configured:
        return Path(configured)
    if os.getenv("VERCEL"):
        return Path("/tmp/luca-runtime")
    return ROOT / "runtime"


RUNTIME_DIR = _runtime_dir()


def _load_catalog() -> tuple[CatalogRepository, str, DataHubMcpCatalog | None]:
    mode = os.getenv("LUCA_CATALOG_MODE") or os.getenv("CONSUMERGRAPH_CATALOG_MODE", "demo")
    mode = mode.lower()
    if mode == "demo":
        return CatalogRepository(ROOT / "data" / "demo_graph.json"), mode, None
    if mode != "mcp":
        raise RuntimeError("LUCA_CATALOG_MODE must be 'demo' or 'mcp'")
    url = os.environ.get("DATAHUB_MCP_URL")
    urn = os.environ.get("DATAHUB_SOURCE_URN")
    if not url or not urn:
        raise RuntimeError("DATAHUB_MCP_URL and DATAHUB_SOURCE_URN are required in MCP catalog mode")
    client = McpClient(url, token=os.environ.get("DATAHUB_MCP_TOKEN"))
    adapter = DataHubMcpCatalog(client)
    return adapter.load(urn), mode, adapter


catalog, catalog_mode, mcp_adapter = _load_catalog()
engine = LucaEngine(catalog)

app = FastAPI(title="ChangeSafe by Luca", version="0.2.0")
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


@app.post("/api/change/package/download")
def download_change_package(request: ChangeRequest, file: str | None = Query(default=None)):
    try:
        if mcp_adapter:
            mcp_adapter.enrich_column(catalog, request.asset_id, request.column)
        analysis = engine.analyze_change(request)
        files = change_package_files(analysis)
        if file is not None:
            if file not in files:
                raise HTTPException(404, "Package file not found")
            media_type = "application/json" if file.endswith(".json") else "text/markdown" if file.endswith(".md") else "text/plain"
            filename = Path(file).name
            return Response(
                files[file],
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        archive = change_package_archive(analysis)
        return StreamingResponse(
            BytesIO(archive),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="changesafe-review-package.zip"'},
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
