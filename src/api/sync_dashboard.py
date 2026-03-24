"""Sync monitoring dashboard API endpoints."""

import os
from typing import List

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter

from src.services.sync.sync_monitor import get_sync_dashboard, ensure_sync_state_columns

router = APIRouter(tags=["sync-monitoring"])


def _get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )


@router.get("/sync/dashboard")
async def sync_dashboard() -> List[dict]:
    """Return sync status for all tenants.

    Each entry contains: tenant_id, sync_status, consecutive_failures,
    last_error, last_success_at, alert_level, transactions_synced, etc.
    """
    connection = _get_db_connection()
    try:
        cursor = connection.cursor()
        ensure_sync_state_columns(cursor)
        connection.commit()
        rows = get_sync_dashboard(cursor)
        return rows
    finally:
        connection.close()
