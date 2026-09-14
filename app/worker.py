import os

from celery import Celery
from celery.schedules import crontab


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)


celery_app = Celery(
    "rule_intelligence_engine",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        # Run retention cleanup daily at 2:00 AM UTC
        'retention-cleanup-daily': {
            'task': 'retention.cleanup',
            'schedule': crontab(hour=2, minute=0),
        },
    }
)