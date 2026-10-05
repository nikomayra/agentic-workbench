from celery import Celery

from app.config import configure_agents, settings

celery_app = Celery(
    "agentic_workbench",
    broker=settings.redis_url,
    include=["app.tasks.workflow_tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    beat_schedule={
        "recover-stale-workflows": {
            "task": "workflows.recover_stale",
            "schedule": 60.0,
        }
    },
    broker_connection_retry_on_startup=True,
    task_acks_late=True,
    task_ignore_result=True,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    worker_prefetch_multiplier=1,
)

# The Celery process does not import app.main, so initialize the Agents SDK here.
configure_agents()
