from celery import Celery

from app.config import configure_agents, settings

celery_app = Celery(
    "agentic_workbench",
    broker=settings.redis_url,
    include=["app.tasks.workflow_tasks"],
)
celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    task_ignore_result=True,
    task_serializer="json",
)

# The Celery process does not import app.main, so initialize the Agents SDK here.
configure_agents()
