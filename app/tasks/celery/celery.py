from app.config import get_settings
from celery import Celery

from app.logging import setup_logging

settings = get_settings()
setup_logging()

app = Celery(
    "celery", broker=settings.celery_broker_url, backend=settings.celery_result_backend
)


app.conf.update(worker_hijack_root_logger=False)
app.conf.update(enable_utc=True, include="app.tasks.celery.tasks")
