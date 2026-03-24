import logging

from src.workers.celery_app import celery_app
from scripts.reconciliation_sync import run_sync

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


@celery_app.task(name="reconciliation.sync_transactions", bind=True, max_retries=MAX_RETRIES)
def reconciliation_sync_task(self, tenant_id: str, api_url: str, bank_account_api_url: str | None = None) -> dict:
    """Run sync with exponential backoff retries (2^attempt seconds)."""
    try:
        return run_sync(tenant_id, api_url, bank_account_api_url)
    except Exception as exc:
        countdown = 2 ** self.request.retries  # 1, 2, 4, 8, 16 seconds
        logger.warning(
            "Sync failed (attempt %d/%d), retrying in %ds: %s",
            self.request.retries + 1, MAX_RETRIES, countdown, exc,
        )
        raise self.retry(exc=exc, countdown=countdown)
