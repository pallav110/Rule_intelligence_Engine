import os
import sys as _sys
if "/app" not in _sys.path:
    _sys.path.insert(0, "/app")

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init


@worker_process_init.connect
def _fix_worker_syspath(**kwargs):
    # Billiard's fork replaces '' with /usr/local/bin, dropping the
    # cwd-based import for the rie_ml top-level package at /app/rie_ml.
    # This signal runs in every ForkPoolWorker child after fork.
    import sys as _s
    if "/app" not in _s.path:
        _s.path.insert(0, "/app")


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