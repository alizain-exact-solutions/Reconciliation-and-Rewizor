"""Database operations for invoices and reconciliation."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor

logger = logging.getLogger(__name__)


def insert_invoice(cursor, invoice_data: Dict[str, Any]) -> int:
    """Insert an extracted invoice into the invoices table. Returns invoice_id."""
    cursor.execute(
        """
        INSERT INTO invoices (
            invoice_number, total_amount, currency, vat_amount,
            gross_amount, net_amount, date, vendor, customer, status, payment_status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING invoice_id
        """,
        (
            invoice_data.get("invoice_number"),
            invoice_data.get("total_amount"),
            invoice_data.get("currency", "PLN"),
            invoice_data.get("vat_amount"),
            invoice_data.get("gross_amount"),
            invoice_data.get("net_amount"),
            invoice_data.get("date"),
            invoice_data.get("vendor"),
            invoice_data.get("customer"),
            "PENDING",
            "UNPAID",
        ),
    )
    row = cursor.fetchone()
    return row[0]


def get_pending_invoices(cursor) -> List[Dict[str, Any]]:
    """Fetch all invoices with status PENDING."""
    cursor.execute(
        """
        SELECT invoice_id, invoice_number, total_amount, currency,
               vat_amount, gross_amount, net_amount, date, vendor, customer
        FROM invoices
        WHERE status = 'PENDING'
        ORDER BY invoice_id
        """
    )
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_unmatched_transactions(cursor) -> List[Dict[str, Any]]:
    """Fetch all transactions with reconciliation_status UNMATCHED."""
    cursor.execute(
        """
        SELECT transaction_id, amount, ref_number, operation_date,
               booking_date, description, partner_name, payment_details
        FROM transactions
        WHERE reconciliation_status = 'UNMATCHED'
        ORDER BY transaction_id
        """
    )
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _compute_payment_status(score: Optional[float]) -> str:
    if score is None:
        return "UNPAID"
    if score >= 80:
        return "PAID"
    if score >= 60:
        return "PENDING"
    return "UNPAID"


def save_match_results(cursor, matches: List[Dict[str, Any]]) -> int:
    """Save matching results to reconciliation_log and update statuses."""
    saved = 0
    for match in matches:
        invoice_number = match.get("invoice_number")
        if not invoice_number:
            continue

        # Look up invoice_id by invoice_number
        cursor.execute(
            "SELECT invoice_id FROM invoices WHERE invoice_number = %s AND status = 'PENDING' LIMIT 1",
            (invoice_number,),
        )
        inv_row = cursor.fetchone()
        if not inv_row:
            continue
        invoice_id = inv_row[0]

        payment_status = _compute_payment_status(match.get("score"))
        cursor.execute(
            "UPDATE invoices SET payment_status = %s WHERE invoice_id = %s",
            (payment_status, invoice_id),
        )

        if match.get("status") != "matched":
            continue

        # Look up transaction_id from the match data
        transaction_number = match.get("transaction_number")
        if not transaction_number:
            continue

        cursor.execute(
            "SELECT transaction_id FROM transactions WHERE transaction_id = %s LIMIT 1",
            (transaction_number,),
        )
        tx_row = cursor.fetchone()
        if not tx_row:
            continue
        transaction_id = tx_row[0]

        # Insert reconciliation record
        cursor.execute(
            """
            INSERT INTO reconciliation_log (invoice_id, transaction_id, match_method, matched_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
            """,
            (invoice_id, transaction_id, f"matching_engine_score_{match.get('score', 0)}"),
        )

        # Update invoice status
        cursor.execute(
            "UPDATE invoices SET status = 'MATCHED', payment_status = %s WHERE invoice_id = %s",
            (payment_status, invoice_id),
        )

        # Update transaction reconciliation status
        cursor.execute(
            "UPDATE transactions SET reconciliation_status = 'MATCHED' WHERE transaction_id = %s",
            (transaction_id,),
        )

        saved += 1

    return saved
