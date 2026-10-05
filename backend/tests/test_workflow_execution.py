import asyncio
import datetime
import uuid
from contextlib import asynccontextmanager

import app.services.workflow_execution as execution_module
import app.tasks.workflow_tasks as task_module


def test_duplicate_delivery_does_not_advance_workflow(monkeypatch):
    """A task that loses the atomic claim must stop before doing agent work."""
    continued = False

    @asynccontextmanager
    async def fake_db_context():
        yield object()

    async def fake_claim(_run_id, _db):
        return None

    async def fake_continue(_workflow_run, _db):
        nonlocal continued
        continued = True

    monkeypatch.setattr(execution_module, "get_async_db_ctx", fake_db_context)
    monkeypatch.setattr(execution_module, "_claim_queued_workflow", fake_claim)
    monkeypatch.setattr(execution_module, "_continue_workflow", fake_continue)

    claimed = asyncio.run(execution_module.advance_workflow(uuid.uuid4()))

    assert claimed is False
    assert continued is False


def test_stale_recovery_enqueues_each_released_workflow(monkeypatch):
    """Database recovery must publish fresh tasks for every released claim."""
    recovered_ids = [uuid.uuid4(), uuid.uuid4()]
    enqueued_ids: list[uuid.UUID] = []
    observed_cutoff: datetime.datetime | None = None

    async def fake_requeue(before):
        nonlocal observed_cutoff
        observed_cutoff = before
        return recovered_ids

    monkeypatch.setattr(task_module, "requeue_stale_workflows", fake_requeue)
    monkeypatch.setattr(task_module, "enqueue_workflow", enqueued_ids.append)

    task_module._recover_stale_workflows_task()

    assert enqueued_ids == recovered_ids
    assert observed_cutoff is not None
    assert observed_cutoff.tzinfo == datetime.UTC
