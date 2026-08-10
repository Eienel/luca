from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    type: str
    nullable: bool = True


class Asset(BaseModel):
    id: str
    urn: str | None = None
    name: str
    type: str
    platform: str
    owner: str
    domain: str
    criticality: int = Field(default=1, ge=1, le=5)
    columns: list[Column] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)


class Edge(BaseModel):
    source: str
    target: str
    hops: int = Field(default=1, ge=1)
    column_map: dict[str, list[str]] = Field(default_factory=dict)


class Catalog(BaseModel):
    assets: list[Asset]
    edges: list[Edge]


class ChangeRequest(BaseModel):
    asset_id: str
    kind: Literal["rename", "remove", "type_change"]
    column: str
    new_name: str | None = None
    new_type: str | None = None
    replacement_relation: str | None = None


class WritebackRequest(BaseModel):
    analysis: dict


class CampaignCreateRequest(BaseModel):
    decision_id: str = Field(min_length=1, max_length=200)
    reviewed_by: str = Field(min_length=1, max_length=200)
    review_approved: bool
    due_at: datetime | None = None


class CampaignTaskUpdate(BaseModel):
    status: Literal["acknowledged", "blocked", "completed", "reassigned"]
    actor: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    new_owner: str | None = Field(default=None, max_length=200)


class CampaignGitHubDispatchRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=200)
