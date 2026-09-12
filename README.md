# Agentic Workbench

## Run the application

### 1. Start PostgreSQL

From this directory:

```bash
docker compose up -d db
```

### 2. Start the backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

API: `http://localhost:8000`, docs: `http://localhost:8000/docs`.

### 3. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:5173`

### Stop everything

```bash
docker compose down
```

Add `-v` to also delete the database volume.

## Tests / lint

```bash
cd backend && uv run pytest && uv run ruff check .
cd frontend && npm run test && npm run lint && npm run build
```

## Migrations

After changing a model in `backend/app/models/`:

```bash
cd backend
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```
