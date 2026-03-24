"""Invoice upload and reconciliation API endpoints."""

import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from src.services.invoice.invoice_processing_pipeline import process_invoice, run_matching_only

logger = logging.getLogger(__name__)

router = APIRouter(tags=["invoices"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def _validate_extension(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return ext


@router.post("/invoices/upload")
async def upload_invoice(file: UploadFile = File(...)):
    """
    Upload an invoice (PDF or image), run OCR to extract data,
    store it in the database, and trigger the matching engine.

    Returns the extracted invoice data and matching results.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = _validate_extension(file.filename)

    # Save to a unique filename to avoid collisions
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        with open(file_path, "wb") as f:
            f.write(contents)

        logger.info("Saved uploaded file to %s", file_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save uploaded file: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Run the pipeline synchronously (for immediate feedback)
    try:
        result = process_invoice(file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Invoice file not found after upload")
    except Exception as e:
        logger.error("Invoice processing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Invoice processing failed: {e}")

    return {
        "message": "Invoice processed successfully",
        "file": unique_name,
        "invoice_data": result["invoice_data"],
        "invoice_id": result["invoice_id"],
        "matching_results": {
            "matched_count": result["matching_results"]["matched_count"],
            "unmatched_count": result["matching_results"]["unmatched_count"],
            "discrepancy_count": result["matching_results"]["discrepancy_count"],
            "total_count": result["matching_results"]["total_count"],
            "reconciled_count": result["matching_results"]["reconciled_count"],
        },
    }


@router.post("/invoices/upload/async")
async def upload_invoice_async(file: UploadFile = File(...)):
    """
    Upload an invoice and process it asynchronously via Celery.
    Returns a task ID to check status later.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = _validate_extension(file.filename)

    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        with open(file_path, "wb") as f:
            f.write(contents)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save uploaded file: %s", e)
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Dispatch to Celery
    from src.workers.tasks.invoice_processing_task import process_invoice_task

    task = process_invoice_task.delay(file_path)

    return {
        "message": "Invoice uploaded and queued for processing",
        "file": unique_name,
        "task_id": task.id,
    }


@router.post("/reconciliation/run")
async def run_reconciliation():
    """
    Re-run the matching engine on all pending invoices
    against unmatched transactions.
    """
    try:
        result = run_matching_only()
    except Exception as e:
        logger.error("Reconciliation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {e}")

    return {
        "message": "Reconciliation complete",
        "matched_count": result["matched_count"],
        "unmatched_count": result["unmatched_count"],
        "discrepancy_count": result["discrepancy_count"],
        "total_count": result["total_count"],
        "reconciled_count": result["reconciled_count"],
    }
