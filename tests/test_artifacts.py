from pathlib import Path
import subprocess

from app.artifacts import write_change_package
from app.catalog import CatalogRepository
from app.engine import LucaEngine
from app.git_workflow import commit_change_package
from app.models import ChangeRequest


ROOT = Path(__file__).resolve().parents[1]


def test_change_package_is_complete_and_reviewable(tmp_path):
    engine = LucaEngine(CatalogRepository(ROOT / "data" / "demo_graph.json"))
    analysis = engine.analyze_change(
        ChangeRequest(asset_id="customer_360", kind="rename", column="customer_id", new_name="buyer_id")
    )
    manifest = write_change_package(analysis, tmp_path)
    package = Path(manifest["directory"])

    assert manifest["review_status"] == "human_review_required"
    assert set(manifest["files"]) == {
        "MIGRATION.md",
        "impact.json",
        "models/compatibility_view.sql",
        "tests/change_regression.sql",
    }
    assert "buyer_id AS customer_id" in (package / "models" / "compatibility_view.sql").read_text()
    assert "Coverage warning" in (package / "MIGRATION.md").read_text()


def test_reviewed_package_becomes_a_real_git_commit(tmp_path):
    engine = LucaEngine(CatalogRepository(ROOT / "data" / "demo_graph.json"))
    analysis = engine.analyze_change(
        ChangeRequest(asset_id="customer_360", kind="rename", column="customer_id", new_name="buyer_id")
    )
    package = Path(write_change_package(analysis, tmp_path / "packages")["directory"])
    repository = tmp_path / "target"
    repository.mkdir()

    def git(*args):
        return subprocess.run(["git", *args], cwd=repository, check=True, capture_output=True, text=True).stdout.strip()

    git("init")
    git("config", "user.email", "changesafe@example.test")
    git("config", "user.name", "ChangeSafe Test")
    (repository / "README.md").write_text("# fixture\n")
    git("add", "README.md")
    git("commit", "-m", "Initial fixture")

    result = commit_change_package(package, repository)
    assert result["branch"].startswith("changesafe/")
    assert git("rev-parse", "HEAD") == result["commit"]
    assert "Apply ChangeSafe migration" in git("log", "-1", "--pretty=%s")
    assert (repository / result["files"][0]).is_file()
