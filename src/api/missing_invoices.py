"""Missing invoice alert endpoints."""

import os
from datetime import datetime
from typing import List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query

from src.repositories.reconciliation_repo import get_missing_invoice_transactions
from src.services.transactions.transaction_categorizer import categorize_transaction

router = APIRouter(tags=["missing-invoices"])


def _get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}") from exc


@router.get("/missing-invoices")
async def missing_invoices(
    start_date: Optional[str] = Query(None, description="ISO start date"),
    end_date: Optional[str] = Query(None, description="ISO end date"),
    grace_days: int = Query(3, ge=0, le=30, description="Grace period before alerting"),
) -> List[dict]: 
    """Return transactions that have no linked invoice (alerts)."""
    connection = _get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        rows = get_missing_invoice_transactions(
            cursor,
            start_date=_parse_date(start_date),
            end_date=_parse_date(end_date),
            grace_days=grace_days,
        )

        alerts = []
        for row in rows:
            categories = list(categorize_transaction(row))
            if categories:
                continue
            alerts.append(
                {
                    "transaction_id": row.get("transaction_id"),
                    "account_id": row.get("account_id"),
                    "amount": row.get("amount"),
                    "operation_date": row.get("operation_date"),
                    "booking_date": row.get("booking_date"),
                    "description": row.get("description"),
                    "partner_name": row.get("partner_name"),
                    "ref_number": row.get("ref_number"),
                    "reason": "missing_invoice",
                }
            )
        return alerts
    finally:
        connection.close()
