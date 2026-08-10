from pathlib import Path

from app.catalog import CatalogRepository
from app.engine import LucaEngine
from app.models import ChangeRequest

ROOT = Path(__file__).resolve().parents[1]


def engine():
    return LucaEngine(CatalogRepository(ROOT / "data" / "demo_graph.json"))


def test_convergence_crosses_teams_and_domains():
    result = engine().convergence("customer_360")
    assert result["score"] >= 80
    assert result["summary"]["teams"] >= 5
    assert result["summary"]["models"] == 1


def test_contract_infers_customer_id_as_join_and_group_key():
    result = engine().infer_contract("customer_360")
    customer_id = next(item for item in result["dependencies"] if item["column"] == "customer_id")
    assert customer_id["confidence"] == "high"
    assert "join_key" in customer_id["roles"]
    assert "grouping_key" in customer_id["roles"]


def test_rename_generates_compatibility_alias_and_finds_consumers():
    result = engine().analyze_change(ChangeRequest(asset_id="customer_360", kind="rename", column="customer_id", new_name="buyer_id"))
    assert result["verdict"] == "migration_required"
    assert "buyer_id AS customer_id" in result["generated"]["compatibility_sql"]
    assert len(result["known_affected_consumers"]) >= 4


def test_remove_is_blocked_when_consumers_exist():
    result = engine().analyze_change(ChangeRequest(asset_id="customer_360", kind="remove", column="customer_id"))
    assert result["approval_recommendation"] == "block_until_manual_plan"
    assert "migration plan required" in result["generated"]["regression_tests"]


def test_type_change_generates_cast_and_is_blocked_for_known_consumers():
    result = engine().analyze_change(
        ChangeRequest(asset_id="customer_360", kind="type_change", column="customer_id", new_type="BIGINT")
    )
    assert result["verdict"] == "migration_required"
    assert result["approval_recommendation"] == "block_until_manual_plan"
    assert "CAST(customer_id AS BIGINT) AS customer_id" in result["generated"]["compatibility_sql"]
    assert "TRY_CAST(customer_id AS BIGINT)" in result["generated"]["regression_tests"]
