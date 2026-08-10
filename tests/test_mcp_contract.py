from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.datahub_mcp import DataHubMcpCatalog
from app.engine import LucaEngine
from app.mcp_client import McpClient
from app.models import ChangeRequest
from app.writeback import save_writeback


SOURCE = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.customer_360,PROD)"
CONSUMERS = {
    "finance": "SELECT customer_id, SUM(lifetime_value) FROM customer_360 GROUP BY customer_id",
    "growth": "SELECT customer_id FROM customer_360 WHERE customer_id IS NOT NULL",
    "support": "SELECT customer_id FROM customer_360",
    "ml_features": "SELECT customer_id, lifetime_value FROM customer_360",
}


def _urn(name: str) -> str:
    return f"urn:li:dataset:(urn:li:dataPlatform:dbt,{name},PROD)"


class DataHubContractHandler(BaseHTTPRequestHandler):
    calls: list[dict] = []

    def log_message(self, format, *args):
        return

    def _send(self, status: int, payload: dict | None = None, session: bool = False):
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if session:
            self.send_header("Mcp-Session-Id", "contract-session")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        message = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.__class__.calls.append(message)
        if message["method"] == "notifications/initialized":
            self._send(202)
            return
        if message["method"] == "initialize":
            self._send(
                200,
                {"jsonrpc": "2.0", "id": message["id"], "result": {"protocolVersion": "2025-03-26", "capabilities": {}, "serverInfo": {"name": "datahub-contract", "version": "1"}}},
                session=True,
            )
            return
        params = message["params"]
        name = params["name"]
        arguments = params["arguments"]
        if name == "get_entities":
            urns = arguments["urns"]
            entities = [
                {"urn": urn, "name": "analytics.customer_360" if urn == SOURCE else urn.split(",")[1], "type": "DATASET", "platform": {"name": "dbt"}, "owner": "Data Team", "domain": "Customer"}
                for urn in urns
            ]
            result = {"structuredContent": {"entities": entities}}
        elif name == "list_schema_fields":
            result = {"structuredContent": {"fields": [{"fieldPath": "customer_id", "type": "STRING", "nullable": False}, {"fieldPath": "lifetime_value", "type": "DECIMAL"}]}}
        elif name == "get_lineage":
            search_results = [
                {
                    "entity": {"urn": _urn(key), "name": key, "type": "DATASET"},
                    "degree": 1,
                    **({"lineageColumns": ["customer_id"]} if arguments.get("column") else {}),
                }
                for key in CONSUMERS
            ]
            result = {"structuredContent": {"downstreams": {"searchResults": search_results}}}
        elif name == "get_dataset_queries":
            result = {
                "structuredContent": {
                    "queries": [
                        {"properties": {"statement": {"value": sql, "language": "SQL"}}}
                        for sql in CONSUMERS.values()
                    ]
                }
            }
        elif name == "save_document":
            result = {"structuredContent": {"urn": "urn:li:document:changesafe-decision"}}
        else:
            result = {"isError": True, "content": [{"type": "text", "text": f"unexpected tool {name}"}]}
        self._send(200, {"jsonrpc": "2.0", "id": message["id"], "result": result})


def test_streamable_http_datahub_contract_and_change_analysis():
    DataHubContractHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), DataHubContractHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = McpClient(f"http://127.0.0.1:{server.server_port}/mcp")
        adapter = DataHubMcpCatalog(client)
        repository = adapter.load(SOURCE)
        source_id = repository.catalog.assets[0].id
        adapter.enrich_column(repository, source_id, "customer_id")
        analysis = LucaEngine(repository).analyze_change(
            ChangeRequest(asset_id=source_id, kind="rename", column="customer_id", new_name="buyer_id")
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)

    methods = [call["method"] for call in DataHubContractHandler.calls]
    tools = [call["params"]["name"] for call in DataHubContractHandler.calls if call["method"] == "tools/call"]
    assert methods[:2] == ["initialize", "notifications/initialized"]
    assert tools[:4] == ["get_entities", "list_schema_fields", "get_dataset_queries", "get_lineage"]
    assert tools.count("get_dataset_queries") == 1
    assert tools.count("get_lineage") == 2
    lineage_calls = [call for call in DataHubContractHandler.calls if call.get("params", {}).get("name") == "get_lineage"]
    assert lineage_calls[0]["params"]["arguments"]["upstream"] is False
    assert lineage_calls[1]["params"]["arguments"]["column"] == "customer_id"
    assert analysis["verdict"] == "migration_required"
    assert len(analysis["known_affected_consumers"]) == 4
    assert "buyer_id AS customer_id" in analysis["generated"]["compatibility_sql"]


def test_mcp_writeback_matches_official_save_document_schema(tmp_path, monkeypatch):
    DataHubContractHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), DataHubContractHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("LUCA_MODE", "mcp")
    monkeypatch.setenv("DATAHUB_MCP_URL", f"http://127.0.0.1:{server.server_port}/mcp")
    analysis = {
        "change": {"asset_id": "customer_360", "column": "customer_id", "kind": "rename"},
        "source": {"name": "customer_360", "urn": SOURCE},
        "verdict": "migration_required",
        "severity": "high",
        "known_affected_consumers": [],
        "generated": {"compatibility_sql": "SELECT 1;", "regression_tests": "SELECT 0;"},
        "unknown_coverage": "Unknown consumers may exist.",
    }
    try:
        saved = save_writeback(analysis, tmp_path)
    finally:
        server.shutdown()
        thread.join(timeout=2)

    save_call = next(call for call in DataHubContractHandler.calls if call.get("params", {}).get("name") == "save_document")
    arguments = save_call["params"]["arguments"]
    assert arguments["document_type"] == "Decision"
    assert arguments["content"].startswith("# Luca change decision")
    assert arguments["related_assets"] == [SOURCE]
    assert "text" not in arguments
    assert saved["mode"] == "mcp"
