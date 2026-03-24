"""Repository helpers for reconciliation reporting and alerts."""

from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from psycopg2.extras import RealDictCursor


def get_missing_invoice_transactions(
    cursor,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    grace_days: int = 3,
) -> List[Dict[str, Any]]:
    """Transactions without a linked invoice, optionally filtered by date range."""
    conditions: List[str] = [
        "t.reconciliation_status = 'UNMATCHED'",
        "NOT EXISTS (SELECT 1 FROM reconciliation_log r WHERE r.transaction_id = t.transaction_id)",
    ]
    params: List[Any] = []

    if start_date:
        conditions.append("t.operation_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("t.operation_date <= %s")
        params.append(end_date)

    # Grace period: ignore very recent transactions
    if grace_days and grace_days > 0:
        conditions.append("t.operation_date <= NOW() - (%s || ' days')::interval")
        params.append(grace_days)

    where_clause = " AND ".join(conditions)
    cursor.execute(
        f"""
        SELECT t.transaction_id, t.account_id, t.amount, t.ref_number,
               t.operation_date, t.booking_date, t.description, t.partner_name,
               t.payment_details
        FROM transactions t
        WHERE {where_clause}
        ORDER BY t.operation_date DESC
        """,
        tuple(params),
    )
    return cursor.fetchall()


def get_reconciled_pairs(
    cursor,
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    account_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    conditions: List[str] = []
    params: List[Any] = []

    if start_date:
        conditions.append("t.operation_date >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("t.operation_date <= %s")
        params.append(end_date)
    if account_id:
        conditions.append("t.account_id = %s")
        params.append(account_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(
        f"""
        SELECT r.reconciliation_id, r.match_method, r.matched_at,
               i.invoice_id, i.invoice_number, i.vendor, i.date AS invoice_date,
               i.gross_amount, i.net_amount, i.vat_amount, i.currency,
               t.transaction_id, t.account_id, t.amount, t.operation_date,
               t.booking_date, t.description, t.partner_name, t.ref_number,
               t.payment_details
        FROM reconciliation_log r
        JOIN invoices i ON i.invoice_id = r.invoice_id
        JOIN transactions t ON t.transaction_id = r.transaction_id
        {where_clause}
        ORDER BY r.matched_at DESC
        """,
        tuple(params),
    )
    return cursor.fetchall()
