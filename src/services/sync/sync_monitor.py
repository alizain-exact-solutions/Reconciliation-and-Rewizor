"""Sync monitoring: state machine, failure tracking, and alerting."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ALERT_WARNING_THRESHOLD = 3
ALERT_CRITICAL_THRESHOLD = 5
NO_SUCCESS_CRITICAL_HOURS = 24


def _compute_alert_level(consecutive_failures: int, last_success_at: Optional[datetime]) -> str:
    if consecutive_failures >= ALERT_CRITICAL_THRESHOLD:
        return "critical"
    if consecutive_failures >= ALERT_WARNING_THRESHOLD:
        return "warning"
    if last_success_at:
        now = datetime.now(timezone.utc)
        success_aware = last_success_at.replace(tzinfo=timezone.utc) if last_success_at.tzinfo is None else last_success_at
        if now - success_aware > timedelta(hours=NO_SUCCESS_CRITICAL_HOURS):
            return "critical"
    return "none"


def ensure_sync_state_columns(cursor) -> None:
    """Add state-machine / failure-tracking columns if they don't exist yet."""
    for col, col_type, default in [
        ("sync_status", "TEXT", "'idle'"),
        ("last_sync_started_at", "TIMESTAMP", "NULL"),
        ("consecutive_failures", "INT", "0"),
        ("total_failures", "INT", "0"),
        ("last_error", "TEXT", "NULL"),
        ("last_success_at", "TIMESTAMP", "NULL"),
        ("alert_level", "TEXT", "'none'"),
        ("transactions_synced", "INT", "0"),
        ("accounts_synced", "INT", "0"),
    ]:
        cursor.execute(
            f"ALTER TABLE sync_state ADD COLUMN IF NOT EXISTS {col} {col_type} DEFAULT {default}"
        )


def ensure_transaction_hash_column(cursor) -> None:
    """Add transaction_hash column and dedup index if they don't exist yet."""
    cursor.execute(
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS transaction_hash TEXT"
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_hash
        ON transactions (transaction_hash) WHERE transaction_hash IS NOT NULL
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_dedup_fallback
        ON transactions (account_id, amount, operation_date, ref_number)
        WHERE ref_number IS NOT NULL
        """
    )


def mark_sync_started(cursor, tenant_id: str) -> None:
    """Transition to 'syncing' state."""
    cursor.execute(
        """
        INSERT INTO sync_state (tenant_id, sync_status, last_sync_started_at)
        VALUES (%s, 'syncing', NOW())
        ON CONFLICT (tenant_id) DO UPDATE
        SET sync_status = 'syncing',
            last_sync_started_at = NOW()
        """,
        (tenant_id,),
    )
    logger.info("Sync started for tenant %s", tenant_id)


def mark_sync_success(
    cursor,
    tenant_id: str,
    transactions_synced: int = 0,
    accounts_synced: int = 0,
) -> None:
    """Transition to 'success' state, reset failure counters."""
    cursor.execute(
        """
        UPDATE sync_state
        SET sync_status = 'success',
            consecutive_failures = 0,
            last_error = NULL,
            last_success_at = NOW(),
            last_sync_at = NOW(),
            alert_level = 'none',
            transactions_synced = %s,
            accounts_synced = %s
        WHERE tenant_id = %s
        """,
        (transactions_synced, accounts_synced, tenant_id),
    )
    logger.info(
        "Sync succeeded for tenant %s: %d transactions, %d accounts",
        tenant_id, transactions_synced, accounts_synced,
    )


def mark_sync_failed(cursor, tenant_id: str, error: str) -> None:
    """Transition to 'failed' state, increment failure counters, compute alert level."""
    cursor.execute(
        "SELECT consecutive_failures, last_success_at FROM sync_state WHERE tenant_id = %s",
        (tenant_id,),
    )
    row = cursor.fetchone()
    if row:
        new_failures = (row[0] or 0) + 1
        last_success = row[1]
    else:
        new_failures = 1
        last_success = None

    alert_level = _compute_alert_level(new_failures, last_success)

    cursor.execute(
        """
        INSERT INTO sync_state (
            tenant_id, sync_status, consecutive_failures, total_failures,
            last_error, alert_level, last_sync_at
        )
        VALUES (%s, 'failed', 1, 1, %s, %s, NOW())
        ON CONFLICT (tenant_id) DO UPDATE
        SET sync_status = 'failed',
            consecutive_failures = sync_state.consecutive_failures + 1,
            total_failures = sync_state.total_failures + 1,
            last_error = %s,
            alert_level = %s,
            last_sync_at = NOW()
        """,
        (tenant_id, error, alert_level, error, alert_level),
    )

    if alert_level == "warning":
        logger.warning(
            "ALERT [WARNING] tenant %s: %d consecutive failures — %s",
            tenant_id, new_failures, error,
        )
    elif alert_level == "critical":
        logger.critical(
            "ALERT [CRITICAL] tenant %s: %d consecutive failures — %s",
            tenant_id, new_failures, error,
        )
    else:
        logger.error("Sync failed for tenant %s: %s", tenant_id, error)


def get_sync_dashboard(cursor) -> List[Dict[str, Any]]:
    """Return sync status for all tenants (monitoring dashboard)."""
    cursor.execute(
        """
        SELECT tenant_id, sync_status, consecutive_failures, total_failures,
               last_error, last_success_at, last_sync_started_at, last_sync_at,
               alert_level, transactions_synced, accounts_synced,
               last_processed_id, last_processed_date
        FROM sync_state
        ORDER BY tenant_id
        """
    )
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
