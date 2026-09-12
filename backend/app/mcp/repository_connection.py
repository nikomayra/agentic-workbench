import sys
from pathlib import Path

from agents.mcp import MCPServerStdio

from app.repository.operations import validate_repository_root

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def make_repository_connection(trusted_root: Path) -> MCPServerStdio:
    root = validate_repository_root(trusted_root)

    return MCPServerStdio(
        name="Repository Server",
        params={
            "command": sys.executable,
            "args": ["-m", "app.mcp.repository_server"],
            "cwd": str(BACKEND_ROOT),
            "env": {"REPOSITORY_ROOT": str(root)},
        },
    )
