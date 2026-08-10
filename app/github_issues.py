from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class GitHubIssueReceipt:
    repository: str
    number: int
    url: str
    created: bool


class GitHubIssueAdapter:
    def __init__(
        self,
        repository: str,
        token: str,
        *,
        labels: list[str] | None = None,
        api_url: str = "https://api.github.com",
        opener: Callable = urlopen,
    ):
        if not _REPOSITORY.fullmatch(repository):
            raise ValueError("GitHub repository must use the owner/name format")
        if not token:
            raise ValueError("A GitHub token is required")
        self.repository = repository
        self.token = token
        self.labels = labels or []
        self.api_url = api_url.rstrip("/")
        self._opener = opener

    @classmethod
    def from_env(cls) -> "GitHubIssueAdapter":
        repository = os.environ.get("CONSUMERGRAPH_GITHUB_REPOSITORY", "")
        token = os.environ.get("CONSUMERGRAPH_GITHUB_TOKEN", "")
        labels = [
            item.strip()
            for item in os.environ.get("CONSUMERGRAPH_GITHUB_LABELS", "").split(",")
            if item.strip()
        ]
        if not repository or not token:
            raise RuntimeError(
                "Set CONSUMERGRAPH_GITHUB_REPOSITORY and CONSUMERGRAPH_GITHUB_TOKEN before GitHub dispatch"
            )
        return cls(repository, token, labels=labels)

    def _request(self, method: str, path: str, payload: dict | None = None) -> object:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self.api_url}{path}",
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "ChangeSafe-Change-Campaigns",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with self._opener(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"GitHub API returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError("GitHub API request failed") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("GitHub API returned invalid JSON") from exc

    def ensure_issue(self, *, title: str, body: str, marker: str) -> GitHubIssueReceipt:
        query = urlencode({"state": "all", "per_page": 100})
        existing = self._request("GET", f"/repos/{self.repository}/issues?{query}")
        if not isinstance(existing, list):
            raise RuntimeError("GitHub issue listing returned an unexpected response")
        for item in existing:
            if marker in str(item.get("body") or ""):
                return self._receipt(item, created=False)

        payload = {"title": title, "body": body}
        if self.labels:
            payload["labels"] = self.labels
        created = self._request(
            "POST",
            f"/repos/{self.repository}/issues",
            payload,
        )
        if not isinstance(created, dict):
            raise RuntimeError("GitHub issue creation returned an unexpected response")
        return self._receipt(created, created=True)

    def _receipt(self, payload: dict, *, created: bool) -> GitHubIssueReceipt:
        number = payload.get("number")
        url = payload.get("html_url")
        if not isinstance(number, int) or not isinstance(url, str):
            raise RuntimeError("GitHub issue response did not contain a number and URL")
        return GitHubIssueReceipt(
            repository=self.repository,
            number=number,
            url=url,
            created=created,
        )
