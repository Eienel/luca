from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class McpError(RuntimeError):
    """Raised when an MCP server cannot complete a protocol operation."""


@dataclass
class McpClient:
    url: str
    token: str | None = None
    timeout: float = 20.0
    protocol_version: str = "2025-03-26"

    def __post_init__(self) -> None:
        self._request_id = 0
        self._session_id: str | None = None
        self._initialized = False

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": self.protocol_version,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    @staticmethod
    def _decode(body: bytes, content_type: str) -> dict[str, Any] | None:
        if not body:
            return None
        text = body.decode("utf-8")
        if "text/event-stream" in content_type:
            data_lines = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
            if not data_lines:
                raise McpError("MCP server returned an event stream without a data event")
            text = data_lines[-1]
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise McpError("MCP server returned a non-JSON response") from exc
        if not isinstance(value, dict):
            raise McpError("MCP response must be a JSON object")
        return value

    def _post(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request = Request(
            self.url,
            data=json.dumps(message).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self._session_id = session_id
                return self._decode(response.read(), response.headers.get("Content-Type", ""))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise McpError(f"MCP HTTP {exc.code}: {detail[:500]}") from exc
        except URLError as exc:
            raise McpError(f"Could not reach MCP server at {self.url}: {exc.reason}") from exc

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": self._request_id, "method": method}
        if params is not None:
            message["params"] = params
        response = self._post(message)
        if not response:
            raise McpError(f"MCP method {method} returned no response")
        if "error" in response:
            raise McpError(f"MCP method {method} failed: {response['error']}")
        return response.get("result")

    def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {"protocolVersion": self.protocol_version}
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "luca-changesafe", "version": "0.2.0"},
            },
        )
        if isinstance(result, dict) and result.get("protocolVersion"):
            self.protocol_version = str(result["protocolVersion"])
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True
        return result

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._initialized:
            self.initialize()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        if not isinstance(result, dict):
            raise McpError(f"MCP tool {name} returned an invalid result")
        if result.get("isError"):
            raise McpError(f"DataHub tool {name} failed: {result.get('content')}")
        return result
