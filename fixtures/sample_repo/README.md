# Reservations (sample app)

A small, self-contained reservations CRUD app. This is a sandbox target
repository for the workbench's agents to read, search, modify, and run tests
against (Phase 2+) — it is not part of the workbench itself.

Uses SQLite instead of Postgres and has no Alembic/Docker/lint tooling, kept
deliberately small so agents (and `run_tests()`) have nothing extra to set up.

## Run

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

API: `http://localhost:8000`, docs: `http://localhost:8000/docs`.

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173`

## Test

```bash
cd backend
uv run pytest
```

## Endpoints

```text
GET    /health
POST   /reservations
GET    /reservations
GET    /reservations/{id}
PATCH  /reservations/{id}   { "status": "pending" | "confirmed" | "cancelled" }
DELETE /reservations/{id}
```
