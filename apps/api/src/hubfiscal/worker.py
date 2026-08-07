import asyncio
from uuid import UUID

from celery import Celery

from .core.config import get_settings
from .core.database import SessionLocal
from .services.orchestrator import execute_retrieval_job

settings = get_settings()
celery_app = Celery(
    "hubfiscal",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Bahia",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    worker_enable_remote_control=False,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    # RabbitMQ 4 não permite mais global QoS. Celery 5.6 desabilita global
    # QoS automaticamente quando detecta quorum queues.
    task_default_queue="hubfiscal-tasks",
    task_default_queue_type="quorum",
    task_create_missing_queue_type="quorum",
    worker_detect_quorum_queues=True,
    broker_transport_options={"confirm_publish": True},
)


@celery_app.task(
    name="hubfiscal.execute_retrieval",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def execute_retrieval_task(self, job_id: str):
    async def run():
        async with SessionLocal() as db:
            job = await execute_retrieval_job(db, UUID(job_id))
            return {"job_id": str(job.id), "status": job.status}

    return asyncio.run(run())
