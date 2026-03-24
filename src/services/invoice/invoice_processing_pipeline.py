"""
Invoice Processing Pipeline
----------------------------
1. Run OCR on an uploaded invoice file (PDF/image)
2. Store extracted invoice data in the database
3. Fetch unmatched transactions from the database
4. Run the MatchingEngine against the new invoice + existing unmatched transactions
5. Persist match results in reconciliation_log
"""

import logging
import os
from typing import Any, Dict, List

import psycopg2
from dotenv import load_dotenv

from src.services.invoice.ocr_service import DocumentAnalyzerProcessor
from src.services.bank.matching_engine import MatchingEngine
from src.repositories.invoice_repo import (
    insert_invoice,
    get_pending_invoices,
    get_unmatched_transactions,
    save_match_results,
)

logger = logging.getLogger(__name__)
load_dotenv()


def _get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )


def _map_transaction_for_engine(tx: Dict[str, Any]) -> Dict[str, Any]:
    """Map DB transaction row to the format expected by MatchingEngine."""
    return {
        "transaction_id": tx.get("transaction_id"),
        "amount": float(tx["amount"]) if tx.get("amount") is not None else 0,
        "gross_amount": abs(float(tx["amount"])) if tx.get("amount") is not None else 0,
        "date": str(tx["operation_date"]) if tx.get("operation_date") else None,
        "book_date": str(tx["booking_date"]) if tx.get("booking_date") else None,
        "operation_title": tx.get("description") or "",
        "transaction_partner_name": tx.get("partner_name") or "",
        "description": tx.get("description") or "",
        "transaction_number": tx.get("transaction_id"),
        "counterparty_data": tx.get("partner_name") or "",
        "invoice_reference": _extract_invoice_ref(tx.get("payment_details") or ""),
        "payment_details": tx.get("payment_details") or "",
    }


def _extract_invoice_ref(payment_details: str) -> str:
    """Try to extract an invoice reference from payment details.

    Payment details often contain patterns like:
      /FAKTURA 74/2025
      /PROFORMA P/114/2025
    """
    import re

    match = re.search(r"(?:FAKTURA|FV|FA|PROFORMA)\s*[A-Z]?/?(\S+)", payment_details, re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return ""


def _map_invoice_for_engine(inv: Dict[str, Any]) -> Dict[str, Any]:
    """Map DB invoice row to the format expected by MatchingEngine."""
    return {
        "invoice_number": inv.get("invoice_number"),
        "total_amount": float(inv["total_amount"]) if inv.get("total_amount") is not None else 0,
        "gross_amount": float(inv["gross_amount"]) if inv.get("gross_amount") is not None else 0,
        "net_amount": float(inv["net_amount"]) if inv.get("net_amount") is not None else None,
        "vat_amount": float(inv["vat_amount"]) if inv.get("vat_amount") is not None else None,
        "currency": inv.get("currency", "PLN"),
        "date": str(inv["date"]) if inv.get("date") else None,
        "vendor": inv.get("vendor") or "",
    }


def process_invoice(file_path: str) -> Dict[str, Any]:
    """
    Full pipeline: OCR → store → match → persist results.

    Args:
        file_path: Path to the invoice PDF or image file.

    Returns:
        A dict with invoice_data, invoice_id, and matching_results.
    """
    logger.info("Starting invoice processing pipeline for: %s", file_path)

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Invoice file not found: {file_path}")

    # --- Step 1: OCR extraction ---
    ocr = DocumentAnalyzerProcessor()
    invoice_data = ocr.analyze_tax_invoice(file_path)
    logger.info("OCR extracted invoice: %s", invoice_data.get("invoice_number"))

    # --- Step 2: Store invoice in DB ---
    connection = _get_db_connection()
    try:
        cursor = connection.cursor()

        invoice_id = insert_invoice(cursor, invoice_data)
        logger.info("Invoice stored with id=%s", invoice_id)

        # --- Step 3: Fetch pending invoices and unmatched transactions ---
        pending_invoices = get_pending_invoices(cursor)
        unmatched_transactions = get_unmatched_transactions(cursor)

        logger.info(
            "Found %s pending invoices, %s unmatched transactions",
            len(pending_invoices),
            len(unmatched_transactions),
        )

        # --- Step 4: Run MatchingEngine ---
        engine = MatchingEngine()
        invoices_for_engine = [_map_invoice_for_engine(inv) for inv in pending_invoices]
        transactions_for_engine = [_map_transaction_for_engine(tx) for tx in unmatched_transactions]

        matching_results = engine.match_invoices(invoices_for_engine, transactions_for_engine)
        logger.info(
            "Matching complete: %s matched, %s unmatched, %s discrepancies",
            matching_results["matched_count"],
            matching_results["unmatched_count"],
            matching_results["discrepancy_count"],
        )

        # --- Step 5: Persist match results ---
        saved = save_match_results(cursor, matching_results.get("matches", []))
        logger.info("Saved %s reconciliation records", saved)

        connection.commit()

        return {
            "invoice_data": invoice_data,
            "invoice_id": invoice_id,
            "matching_results": {
                "matched_count": matching_results["matched_count"],
                "unmatched_count": matching_results["unmatched_count"],
                "discrepancy_count": matching_results["discrepancy_count"],
                "total_count": matching_results["total_count"],
                "reconciled_count": saved,
                "matches": matching_results["matches"],
            },
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def run_matching_only() -> Dict[str, Any]:
    """
    Run the matching engine on all pending invoices vs unmatched transactions.
    Useful when invoices are already in the DB and you just need to re-run matching.
    """
    logger.info("Running matching engine (no OCR)")

    connection = _get_db_connection()
    try:
        cursor = connection.cursor()

        pending_invoices = get_pending_invoices(cursor)
        unmatched_transactions = get_unmatched_transactions(cursor)

        logger.info(
            "Found %s pending invoices, %s unmatched transactions",
            len(pending_invoices),
            len(unmatched_transactions),
        )

        if not pending_invoices or not unmatched_transactions:
            return {
                "matched_count": 0,
                "unmatched_count": len(pending_invoices),
                "discrepancy_count": 0,
                "total_count": len(pending_invoices),
                "reconciled_count": 0,
                "matches": [],
            }

        engine = MatchingEngine()
        invoices_for_engine = [_map_invoice_for_engine(inv) for inv in pending_invoices]
        transactions_for_engine = [_map_transaction_for_engine(tx) for tx in unmatched_transactions]

        matching_results = engine.match_invoices(invoices_for_engine, transactions_for_engine)

        saved = save_match_results(cursor, matching_results.get("matches", []))
        connection.commit()

        return {
            "matched_count": matching_results["matched_count"],
            "unmatched_count": matching_results["unmatched_count"],
            "discrepancy_count": matching_results["discrepancy_count"],
            "total_count": matching_results["total_count"],
            "reconciled_count": saved,
            "matches": matching_results["matches"],
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()
