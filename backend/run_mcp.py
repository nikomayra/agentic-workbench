import os
from pathlib import Path

from app.schemas.schemas import RepositoryTarget

fixture_root = (Path(__file__).resolve().parent.parent / "fixtures" / "sample_repo").resolve()
fixture_target = RepositoryTarget(
    clone_url=str(fixture_root),
    base_branch="main",
    test_command=["uv", "run", "pytest", "-q"],
    test_working_directory="backend",
)
os.environ.setdefault("REPOSITORY_ROOT", str(fixture_root))
os.environ.setdefault("REPOSITORY_TARGET", fixture_target.model_dump_json())

from app.mcp.repository_server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
