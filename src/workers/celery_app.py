import os

from celery import Celery, signals
from dotenv import load_dotenv

load_dotenv()

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery("finance_workers", broker=broker_url, backend=result_backend)
celery_app.autodiscover_tasks(["src.workers.tasks"])

celery_app.conf.timezone = os.getenv("CELERY_TIMEZONE", "UTC")
celery_app.conf.enable_utc = True

try:
	from src.workers.schedules import CELERY_BEAT_SCHEDULE

	celery_app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
except Exception:
	pass


@signals.worker_ready.connect
def _run_reconciliation_on_startup(sender=None, **kwargs):
	startup_enabled = os.getenv("RECONCILIATION_STARTUP_SYNC", "true").lower() in {
		"1",
		"true",
		"yes",
	}
	if not startup_enabled:
		return

	tenant_id = os.getenv("RECONCILIATION_TENANT_ID", "default")
	api_url = os.getenv("RECONCILIATION_API_URL")
	bank_account_api_url = os.getenv("RECONCILIATION_BANK_ACCOUNT_API_URL")
	if not api_url:
		return

	celery_app.send_task(
		"reconciliation.sync_transactions",
		args=(tenant_id, api_url, bank_account_api_url),
	)
