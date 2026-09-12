# Backend Requirements

## Runtime

- Python 3.14 with [`uv`](https://docs.astral.sh/uv/)
- PostgreSQL and Redis
- Git and `rg` (ripgrep) available to worker processes
- A writable target Git repository with a configured base branch

## Environment

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async PostgreSQL connection |
| `REDIS_URL` | Celery broker/result connection |
| `OPENAI_API_KEY` | Agent model access |
| `GITHUB_TOKEN` | Issue intake and draft pull-request publication |
| `CORS_ORIGINS` | Allowed frontend origins |

The selected repository must define an allowed test command. The bundled fixture uses `backend/` with `uv run pytest -q`; generated worktrees are stored outside the target checkout and are removed at terminal workflow states.

## Commands

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
```

Docker Compose starts the Redis-backed Celery worker alongside the API. Inspect the repository MCP server with `uv run mcp dev run_mcp.py`.

## Constraints

- Repository commands require an execution sandbox before accepting arbitrary untrusted code.
- Workstream paths guide decomposition but do not replace worktree isolation or merge-conflict handling.
- PostgreSQL is the durable source of workflow state; Redis and SSE must not be treated as persistence.
