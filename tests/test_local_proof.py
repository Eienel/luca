from scripts.run_local_proof import run_proof


def test_real_sql_break_is_detected_and_repaired():
    result = run_proof()

    assert result["breaking_change"]["status"] == "failed_as_expected"
    assert "customer_id" in result["breaking_change"]["error"]
    assert result["luca"]["verdict"] == "migration_required"
    assert len(result["luca"]["affected_consumers"]) == 4
    assert "buyer_id AS customer_id" in result["luca"]["generated_compatibility_sql"]
    assert result["repaired"]["status"] == "pass"
    assert result["repaired"]["alias_mismatches"] == 0
