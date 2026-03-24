"""Celery task for async invoice OCR processing and matching."""

from src.workers.celery_app import celery_app
from src.services.invoice.invoice_processing_pipeline import process_invoice, run_matching_only


@celery_app.task(name="invoice.process_and_match", bind=True, max_retries=2)
def process_invoice_task(self, file_path: str) -> dict:
    """Run the full invoice pipeline: OCR → store → match."""
    try:
        return process_invoice(file_path)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="invoice.run_matching")
def run_matching_task() -> dict:
    """Re-run matching on all pending invoices vs unmatched transactions."""
    return run_matching_only()
