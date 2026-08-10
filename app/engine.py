from __future__ import annotations

import re
from collections import defaultdict

from .catalog import CatalogRepository
from .models import Asset, ChangeRequest


def _contains_column(sql: str, column: str) -> bool:
    return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(column)}(?![A-Za-z0-9_])", sql, re.I))


def _roles(sql: str, column: str) -> set[str]:
    roles: set[str] = set()
    normalized = " ".join(sql.lower().split())
    escaped = re.escape(column.lower())
    if re.search(rf"\bjoin\b.+\bon\b.+\b{escaped}\b", normalized):
        roles.add("join_key")
    if re.search(rf"\bgroup\s+by\b.+\b{escaped}\b", normalized):
        roles.add("grouping_key")
    if re.search(rf"\b(sum|avg|min|max|count)\s*\([^)]*\b{escaped}\b", normalized):
        roles.add("aggregate_input")
    if re.search(rf"\bwhere\b.+\b{escaped}\b", normalized):
        roles.add("filter")
    if not roles:
        roles.add("selected")
    return roles


class LucaEngine:
    def __init__(self, catalog: CatalogRepository):
        self.catalog = catalog

    def convergence(self, asset_id: str) -> dict:
        source = self.catalog.get_asset(asset_id)
        downstream = self.catalog.downstream(asset_id)
        direct_ids = {edge.target for edge in self.catalog.outgoing(asset_id) if edge.hops == 1}
        teams = {asset.owner for asset, _ in downstream}
        domains = {asset.domain for asset, _ in downstream}
        dashboards = sum(asset.type == "dashboard" for asset, _ in downstream)
        models = sum(asset.type == "ml_model" for asset, _ in downstream)
        critical = sum(asset.criticality >= 4 for asset, _ in downstream)
        score = min(
            100,
            len(direct_ids) * 7
            + (len(downstream) - len(direct_ids)) * 3
            + len(teams) * 7
            + len(domains) * 8
            + dashboards * 5
            + models * 10
            + critical * 4,
        )
        risk = "critical" if score >= 80 else "high" if score >= 60 else "moderate" if score >= 35 else "low"
        return {
            "asset": source.model_dump(),
            "score": score,
            "risk": risk,
            "summary": {
                "direct_consumers": len(direct_ids),
                "all_consumers": len(downstream),
                "teams": len(teams),
                "domains": len(domains),
                "dashboards": dashboards,
                "models": models,
                "critical_consumers": critical,
            },
            "consumers": [
                {**asset.model_dump(exclude={"queries", "columns"}), "hops": hops}
                for asset, hops in downstream
            ],
        }

    def infer_contract(self, asset_id: str) -> dict:
        source = self.catalog.get_asset(asset_id)
        downstream = self.catalog.downstream(asset_id)
        evidence: dict[str, dict] = {
            column.name: {"queries": 0, "consumers": set(), "roles": set(), "samples": []}
            for column in source.columns
        }
        for query in source.queries:
            for column in source.columns:
                if not _contains_column(query, column.name):
                    continue
                item = evidence[column.name]
                item["queries"] += 1
                item["roles"].update(_roles(query, column.name))
                if len(item["samples"]) < 2:
                    item["samples"].append(query)
        for consumer, _ in downstream:
            for query in consumer.queries:
                for column in source.columns:
                    if not _contains_column(query, column.name):
                        continue
                    item = evidence[column.name]
                    item["queries"] += 1
                    item["consumers"].add(consumer.id)
                    item["roles"].update(_roles(query, column.name))
                    if len(item["samples"]) < 2:
                        item["samples"].append(query)

        dependencies = []
        for column in source.columns:
            item = evidence[column.name]
            consumer_count = len(item["consumers"])
            confidence = "high" if item["queries"] >= 3 or consumer_count >= 3 else "medium" if item["queries"] else "unknown"
            dependencies.append(
                {
                    "column": column.name,
                    "type": column.type,
                    "nullable": column.nullable,
                    "query_evidence": item["queries"],
                    "consumer_count": consumer_count,
                    "consumers": sorted(item["consumers"]),
                    "roles": sorted(item["roles"]),
                    "confidence": confidence,
                    "sample_queries": item["samples"],
                }
            )
        dependencies.sort(key=lambda item: (item["query_evidence"], item["consumer_count"]), reverse=True)
        return {
            "asset": source.model_dump(exclude={"queries"}),
            "dependencies": dependencies,
            "warning": "Observed usage is evidence, not an automatically binding business contract.",
        }

    def analyze_change(self, request: ChangeRequest) -> dict:
        source = self.catalog.get_asset(request.asset_id)
        column = next((item for item in source.columns if item.name == request.column), None)
        if column is None:
            raise ValueError(f"Column {request.column!r} does not exist on {source.name}")
        if request.kind == "rename" and not request.new_name:
            raise ValueError("new_name is required for a rename")
        if request.kind == "type_change" and not request.new_type:
            raise ValueError("new_type is required for a type change")

        contract = self.infer_contract(request.asset_id)
        dependency = next(item for item in contract["dependencies"] if item["column"] == request.column)
        affected: dict[str, dict] = {}
        for asset, hops in self.catalog.downstream(request.asset_id):
            query_hits = [query for query in asset.queries if _contains_column(query, request.column)]
            column_paths = []
            for edge in self.catalog.catalog.edges:
                if edge.target == asset.id and request.column in edge.column_map:
                    column_paths.extend(edge.column_map[request.column])
            if query_hits or column_paths:
                affected[asset.id] = {
                    "id": asset.id,
                    "name": asset.name,
                    "type": asset.type,
                    "owner": asset.owner,
                    "domain": asset.domain,
                    "hops": hops,
                    "query_hits": len(query_hits),
                    "column_paths": column_paths,
                    "criticality": asset.criticality,
                }

        severity_points = len(affected) + sum(item["criticality"] >= 4 for item in affected.values()) * 2
        severity = "critical" if severity_points >= 8 else "high" if severity_points >= 4 else "moderate" if severity_points else "low"
        sql, tests = self._artifacts(source, column.name, request)
        safe = not affected or request.kind == "rename"
        return {
            "change": request.model_dump(),
            "source": source.model_dump(exclude={"queries"}),
            "verdict": "migration_required" if affected else "no_known_breakage",
            "severity": severity,
            "known_affected_consumers": list(affected.values()),
            "dependency_evidence": dependency,
            "unknown_coverage": "Consumers without captured lineage or query history may be missing.",
            "generated": {"compatibility_sql": sql, "regression_tests": tests},
            "approval_recommendation": "review_and_apply" if safe else "block_until_manual_plan",
        }

    @staticmethod
    def _artifacts(source: Asset, column: str, request: ChangeRequest) -> tuple[str, str]:
        other_columns = [item.name for item in source.columns if item.name != column]
        if request.kind == "rename":
            projection = [request.new_name, f"{request.new_name} AS {column}", *other_columns]
            input_relation = request.replacement_relation or source.name
            output_relation = source.name if request.replacement_relation else f"{source.name}_compatible"
            sql = "CREATE OR REPLACE VIEW {0} AS\nSELECT\n    {1}\nFROM {2};".format(
                output_relation, ",\n    ".join(projection), input_relation
            )
            tests = f"SELECT COUNT(*) AS mismatches\nFROM {output_relation}\nWHERE {column} IS DISTINCT FROM {request.new_name};"
        elif request.kind == "remove":
            sql = f"-- BLOCKED: preserve {column} until all known consumers migrate.\n-- Proposed source: {source.name}"
            tests = (
                "-- This executable data test intentionally returns one row while the removal is blocked.\n"
                f"SELECT '{source.name}.{column} has known consumers; migration plan required' AS blocking_reason;"
            )
        else:
            projection = [f"CAST({column} AS {column_type}) AS {column}" if item == column else item for item in [column, *other_columns] for column_type in [request.new_type]]
            sql = "CREATE OR REPLACE VIEW {0}_compatible AS\nSELECT\n    {1}\nFROM {0};".format(source.name, ",\n    ".join(projection))
            tests = f"SELECT COUNT(*) AS invalid_casts\nFROM {source.name}\nWHERE {column} IS NOT NULL AND TRY_CAST({column} AS {request.new_type}) IS NULL;"
        return sql, tests
