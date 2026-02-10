from app.config import get_settings
from celery import Celery

settings = get_settings()

app = Celery(
    "celery", broker=settings.celery_broker_url, backend=settings.celery_result_backend
)


app.conf.update(enable_utc=True, include="app.tasks.celery.tasks")
