import os

from celery.schedules import crontab

RECONCILIATION_TENANT_ID = os.getenv("RECONCILIATION_TENANT_ID", "default")
RECONCILIATION_API_URL = os.getenv("RECONCILIATION_API_URL")
if not RECONCILIATION_API_URL:
    raise ValueError("RECONCILIATION_API_URL must be set in the environment")
RECONCILIATION_BANK_ACCOUNT_API_URL = os.getenv("RECONCILIATION_BANK_ACCOUNT_API_URL")
RECONCILIATION_CRON_HOUR = os.getenv("RECONCILIATION_CRON_HOUR", "*")
RECONCILIATION_CRON_MINUTE = os.getenv("RECONCILIATION_CRON_MINUTE", "0")

CELERY_BEAT_SCHEDULE = {
    "reconciliation-sync": {
        "task": "reconciliation.sync_transactions",
        "schedule": crontab(minute=RECONCILIATION_CRON_MINUTE, hour=RECONCILIATION_CRON_HOUR),
        "args": (RECONCILIATION_TENANT_ID, RECONCILIATION_API_URL, RECONCILIATION_BANK_ACCOUNT_API_URL),
    }
}
