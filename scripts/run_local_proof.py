from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from app.catalog import CatalogRepository
from app.engine import LucaEngine
from app.models import Asset, Catalog, ChangeRequest, Column, Edge


ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "tests" / "fixtures" / "dbt_project" / "models"
CONSUMERS = ("finance_revenue", "growth_segments", "support_priority", "ml_features")


def _sql(name: str) -> str:
    return (MODELS / f"{name}.sql").read_text(encoding="utf-8").strip()


def _render_dbt(sql: str) -> str:
    return re.sub(r"\{\{\s*ref\(['\"]([^'\"]+)['\"]\)\s*\}\}", r"\1", sql)


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE raw_customers (
            id INTEGER PRIMARY KEY,
            segment TEXT NOT NULL,
            lifetime_value REAL NOT NULL
        );
        INSERT INTO raw_customers VALUES
            (1, 'active', 120.0),
            (2, 'at_risk', 55.5),
            (3, 'active', 310.0);
        """
    )
    return connection


def _create_view(connection: sqlite3.Connection, name: str, select_sql: str) -> None:
    connection.execute(f"CREATE VIEW {name} AS {select_sql}")


def _build_consumers(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name in CONSUMERS:
        _create_view(connection, name, _render_dbt(_sql(name)))
        counts[name] = connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    return counts


def _catalog() -> CatalogRepository:
    source = Asset(
        id="customer_360",
        name="customer_360",
        type="dataset",
        platform="dbt",
        owner="Data Platform",
        domain="Customer",
        criticality=5,
        columns=[
            Column(name="customer_id", type="INTEGER", nullable=False),
            Column(name="segment", type="TEXT", nullable=False),
            Column(name="lifetime_value", type="REAL", nullable=False),
        ],
    )
    owners = {
        "finance_revenue": ("Finance", "Finance"),
        "growth_segments": ("Growth", "Marketing"),
        "support_priority": ("Support", "Operations"),
        "ml_features": ("ML Platform", "Machine Learning"),
    }
    consumers = [
        Asset(
            id=name,
            name=name,
            type="dbt_model",
            platform="dbt",
            owner=owners[name][0],
            domain=owners[name][1],
            criticality=4,
            queries=[_render_dbt(_sql(name))],
        )
        for name in CONSUMERS
    ]
    return CatalogRepository.from_catalog(
        Catalog(
            assets=[source, *consumers],
            edges=[Edge(source="customer_360", target=name) for name in CONSUMERS],
        )
    )


def run_proof() -> dict:
    baseline = _connection()
    _create_view(baseline, "customer_360", _sql("customer_360_v1"))
    baseline_counts = _build_consumers(baseline)

    broken = _connection()
    _create_view(broken, "customer_360", _sql("customer_360_v2"))
    broken_error = None
    try:
        _build_consumers(broken)
    except sqlite3.OperationalError as error:
        broken_error = str(error)
    if broken_error is None:
        raise AssertionError("The rename scenario did not break a downstream consumer")

    engine = LucaEngine(_catalog())
    analysis = engine.analyze_change(
        ChangeRequest(
            asset_id="customer_360",
            kind="rename",
            column="customer_id",
            new_name="buyer_id",
            replacement_relation="customer_360_v2",
        )
    )

    repaired = _connection()
    _create_view(repaired, "customer_360_v2", _sql("customer_360_v2"))
    compatibility_sql = analysis["generated"]["compatibility_sql"].replace(
        "CREATE OR REPLACE VIEW", "CREATE VIEW", 1
    )
    repaired.executescript(compatibility_sql)
    repaired_counts = _build_consumers(repaired)
    mismatch_count = repaired.execute(
        "SELECT COUNT(*) FROM customer_360 WHERE customer_id IS NOT buyer_id"
    ).fetchone()[0]

    return {
        "baseline": {"status": "pass", "row_counts": baseline_counts},
        "breaking_change": {"status": "failed_as_expected", "error": broken_error},
        "luca": {
            "verdict": analysis["verdict"],
            "affected_consumers": [item["id"] for item in analysis["known_affected_consumers"]],
            "generated_compatibility_sql": analysis["generated"]["compatibility_sql"],
        },
        "repaired": {
            "status": "pass",
            "row_counts": repaired_counts,
            "alias_mismatches": mismatch_count,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_proof(), indent=2))
