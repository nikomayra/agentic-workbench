# Backend Reference

## Runtime Assumptions

- The target is `fixtures/sample_repo`, with a Git `main` branch and `README.md`.
- Generated worktrees live in `fixtures/.agent_worktrees`.
- Tests expect `<target>/backend` and run with `uv run pytest -q`.
- Run the MCP Inspector from `backend/` with `uv run mcp dev run_mcp.py`.

## Known Limitations

- Repository commands run directly on the host; untrusted repositories need sandboxing.
- The target repository and test command are not configurable through the API.
- Workstream paths are planning guidance, not enforced file-level permissions.
- Process crashes can leave workflow records or temporary Git resources behind.
- Final results remain local; no branch publication or pull request is created.
- Terminal workflow state retains paths to worktrees that cleanup has removed.
