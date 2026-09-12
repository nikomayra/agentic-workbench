import os
from pathlib import Path

from mcp.server import MCPServer

from app.repository import operations as repository

TRUSTED_ROOT = repository.validate_repository_root(
    Path(os.environ.get("REPOSITORY_ROOT", str(repository.SAMPLE_REPOSITORY_ROOT)))
)

mcp = MCPServer(name="Repository Server")


@mcp.resource("docs://readme", mime_type="text/markdown")
def readme() -> str:
    """How to use this repo."""
    return repository.read_file("README.md", TRUSTED_ROOT)


@mcp.prompt()
def review_change() -> str:
    """Instructions for reviewing an integrated software change."""
    return (
        "Inspect the approved workstreams, acceptance criteria, code changes, "
        "and test output before choosing a review status. All P0 and P1 issues "
        "must be addressed. Use discretion for P2 issues, and note but do not "
        "reject based only on P3 issues."
    )


@mcp.tool()
def list_files() -> list[str]:
    """List files beneath the permitted repository root."""
    return repository.list_files(TRUSTED_ROOT)


@mcp.tool()
def read_file(relative_path: str) -> str:
    """Read one text file beneath the permitted repository root."""
    return repository.read_file(relative_path, TRUSTED_ROOT)


@mcp.tool()
def search_repo(query: str) -> str:
    """Search the permitted repository for matching source text."""
    return repository.search_code(query, TRUSTED_ROOT)


@mcp.tool()
def git_diff() -> str:
    """Runs git diff on repository. Provides changes in raw Git format."""
    return repository.git_diff(TRUSTED_ROOT)


@mcp.tool()
def git_status() -> str:
    """Runs git status on repository. Provides changes in raw Git format."""
    return repository.git_status(TRUSTED_ROOT)


@mcp.tool()
def run_tests() -> str:
    """Run the repository backend pytest suite. Provides its exit code and bounded test output."""
    return repository.run_tests(TRUSTED_ROOT)


if __name__ == "__main__":
    mcp.run(transport="stdio")
