import asyncio
import datetime
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import app.services.workflow_execution as execution_module
import app.tasks.workflow_tasks as task_module
from app.orchestration.state import CoordinatorStages
from tests.factories import finalization_state, sample_repository_workspace


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


def test_approved_github_workflow_publishes_and_cleans_workspace(monkeypatch):
    workspace = sample_repository_workspace()
    workflow_run = SimpleNamespace(
        issue_url="https://github.com/example/project/issues/12",
        objective="Validate reservation dates",
        pull_request_url=None,
    )
    published: list[tuple[str, str]] = []
    saved = False
    removed = False

    def fake_finalize(_state, *, approved, workspace):
        assert approved is True
        assert workspace == sample_repository_workspace()
        return finalization_state().model_copy(
            update={"stage": CoordinatorStages.COMPLETED}
        )

    def fake_publish(_workspace, branch, issue_url, _objective, _token):
        published.append((branch, issue_url))
        return "https://github.com/example/project/pull/44"

    async def fake_save(_workflow_run, _execution, _db):
        nonlocal saved
        saved = True

    def fake_remove(_workspace):
        nonlocal removed
        removed = True

    monkeypatch.setattr(
        execution_module,
        "_repository_workspace",
        lambda _workflow_run: workspace,
    )
    monkeypatch.setattr(execution_module, "_saved_coordinator_execution", lambda _: object())
    monkeypatch.setattr(execution_module, "finalize_coordinator", fake_finalize)
    monkeypatch.setattr(execution_module, "publish_draft_pull_request", fake_publish)
    monkeypatch.setattr(execution_module, "_save_coordinator_execution", fake_save)
    monkeypatch.setattr(execution_module, "remove_workspace", fake_remove)

    asyncio.run(execution_module.finalize_workflow(workflow_run, True, object()))

    assert workflow_run.pull_request_url == "https://github.com/example/project/pull/44"
    assert published == [
        (
            finalization_state().integration_worktree.branch,
            workflow_run.issue_url,
        )
    ]
    assert saved is True
    assert removed is True
