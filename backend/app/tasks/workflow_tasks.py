import asyncio
import uuid
from typing import cast

from celery import Task

from app.services.workflow_execution import advance_workflow
from app.tasks.celery_app import celery_app


def _advance_workflow_task(run_id: str) -> None:
    asyncio.run(advance_workflow(uuid.UUID(run_id)))


# Celery turns the decorated function into a Task at runtime, but its decorator
# does not provide enough type information for Pylance to infer that change.
advance_workflow_task = cast(
    Task,
    celery_app.task(name="workflows.advance")(_advance_workflow_task),
)


def enqueue_workflow(run_id: uuid.UUID) -> None:
    """Send one workflow ID to Celery without exposing Celery types to callers."""
    advance_workflow_task.delay(str(run_id))
