import argparse
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_batch
import requests
from dotenv import load_dotenv

from src.services.sync.sync_monitor import (
    ensure_sync_state_columns,
    ensure_transaction_hash_column,
    mark_sync_failed,
    mark_sync_started,
    mark_sync_success,
)

logger = logging.getLogger(__name__)


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def load_config() -> Dict[str, Any]:
    load_dotenv()
    api_key = (
        os.getenv("x_api_key")
        or os.getenv("X_API_KEY")
        or os.getenv("RECONCILIATION_API_KEY")
        or ""
    ).strip()
    return {
        "db_host": os.getenv("DB_HOST"),
        "db_name": os.getenv("DB_NAME"),
        "db_user": os.getenv("DB_USER"),
        "db_password": os.getenv("DB_PASSWORD"),
        "db_port": os.getenv("DB_PORT", "5432"),
        "api_key": api_key or None,
        "page_size": int(os.getenv("RECONCILIATION_PAGE_SIZE", "200")),
    }


def get_db_connection(config: Dict[str, Any]):
    return psycopg2.connect(
        host=config["db_host"],
        dbname=config["db_name"],
        user=config["db_user"],
        password=config["db_password"],
        port=config["db_port"],
    )


def fetch_last_processed_id(cursor, tenant_id: str) -> int:
    cursor.execute(
        "SELECT last_processed_id FROM sync_state WHERE tenant_id = %s",
        (tenant_id,),
    )
    row = cursor.fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def fetch_transactions(
    api_url: str,
    page: int,
    page_size: int,
    api_key: Optional[str],
    modified_from: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    headers = {}
    if api_key:
        # Some gateways expect hyphenated header names, others accept underscores.
        headers["x-api-key"] = api_key
        headers["x_api_key"] = api_key
    params: Dict[str, Any] = {"page": page, "size": page_size}
    # Incremental sync: only fetch transactions modified after last sync
    if modified_from:
        params["from"] = modified_from.isoformat()
    response = requests.get(
        api_url,
        params=params,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON returned from API") from exc

    if not isinstance(data, list):
        raise ValueError("API response must be a list of JSON objects")
    return data


def fetch_bank_accounts(api_url: str, api_key: Optional[str]) -> List[Dict[str, Any]]:
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key
        headers["x_api_key"] = api_key
    response = requests.get(api_url, headers=headers, timeout=30)
    response.raise_for_status()

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON returned from API") from exc

    if not isinstance(data, list):
        raise ValueError("API response must be a list of JSON objects")
    return data


def compute_transaction_hash(item: Dict[str, Any]) -> str:
    """Compute a content-based SHA-256 hash for duplicate detection.

    Uses (account_id, amount, operation_date, ref_number, description) so that
    re-sent data with a different transactionId is still detected as a duplicate.
    """
    parts = [
        str(item.get("transactionAccountId", "")),
        str(item.get("transactionAmount", "")),
        str(item.get("transactionOperationDate", "")),
        str(item.get("transactionRefNumber", "")),
        str(item.get("transactionDescription", "")),
    ]
    canonical = "|".join(parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def map_transaction(item: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        item.get("transactionId"),
        item.get("transactionAccountId"),
        item.get("transactionAmount"),
        item.get("transactionRefNumber"),
        parse_iso_datetime(item.get("transactionOperationDate")),
        parse_iso_datetime(item.get("transactionBookingDate")),
        item.get("transactionDescription"),
        item.get("transactionPartnerName"),
        item.get("transactionPaymentDetails"),
        parse_iso_datetime(item.get("modifiedOn")),
        compute_transaction_hash(item),
    )


def map_bank_account(item: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        item.get("accountId"),
        item.get("accountName"),
        item.get("accountNumber"),
        item.get("accountProviderId"),
        item.get("accountGroupId"),
        item.get("accountBalance"),
        item.get("accountAvailableFunds"),
        item.get("accountPrevBalance"),
        item.get("accountPrevAvailableFunds"),
        item.get("timeStamp"),
        parse_iso_datetime(item.get("createdOn")),
        parse_iso_datetime(item.get("modifiedOn")),
        item.get("accountCurrency"),
        item.get("accountIsClosed"),
    )


def upsert_transactions(cursor, transactions: Iterable[Dict[str, Any]]) -> Tuple[int, Optional[datetime]]:
    rows = [map_transaction(item) for item in transactions]
    if not rows:
        return 0, None

    # Skip transactions whose hash already exists (idempotency)
    hashes = [row[10] for row in rows if row[10]]
    if hashes:
        cursor.execute(
            "SELECT transaction_hash FROM transactions WHERE transaction_hash = ANY(%s)",
            (hashes,),
        )
        existing_hashes = {r[0] for r in cursor.fetchall()}
        rows = [row for row in rows if row[10] not in existing_hashes]

    if not rows:
        return 0, None

    sql = """
        INSERT INTO transactions (
            transaction_id,
            account_id,
            amount,
            ref_number,
            operation_date,
            booking_date,
            description,
            partner_name,
            payment_details,
            modified_on,
            transaction_hash
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (transaction_id) DO UPDATE
        SET
            account_id = EXCLUDED.account_id,
            amount = EXCLUDED.amount,
            ref_number = EXCLUDED.ref_number,
            operation_date = EXCLUDED.operation_date,
            booking_date = EXCLUDED.booking_date,
            description = EXCLUDED.description,
            partner_name = EXCLUDED.partner_name,
            payment_details = EXCLUDED.payment_details,
            modified_on = EXCLUDED.modified_on,
            transaction_hash = EXCLUDED.transaction_hash
        WHERE EXCLUDED.modified_on IS NOT NULL
          AND (transactions.modified_on IS NULL OR EXCLUDED.modified_on > transactions.modified_on)
    """

    execute_batch(cursor, sql, rows, page_size=200)

    max_id = 0
    max_date = None
    for row in rows:
        if row[0] is not None and row[0] > max_id:
            max_id = row[0]
        if row[9] and (max_date is None or row[9] > max_date):
            max_date = row[9]
    return max_id, max_date


def upsert_bank_accounts(cursor, accounts: Iterable[Dict[str, Any]]) -> int:
    rows = [map_bank_account(item) for item in accounts]
    if not rows:
        return 0

    sql = """
        INSERT INTO bank_accounts (
            account_id,
            account_name,
            account_number,
            account_provider_id,
            account_group_id,
            account_balance,
            account_available_funds,
            account_prev_balance,
            account_prev_available_funds,
            time_stamp,
            created_on,
            modified_on,
            account_currency,
            account_is_closed
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (account_id) DO UPDATE
        SET
            account_name = EXCLUDED.account_name,
            account_number = EXCLUDED.account_number,
            account_provider_id = EXCLUDED.account_provider_id,
            account_group_id = EXCLUDED.account_group_id,
            account_balance = EXCLUDED.account_balance,
            account_available_funds = EXCLUDED.account_available_funds,
            account_prev_balance = EXCLUDED.account_prev_balance,
            account_prev_available_funds = EXCLUDED.account_prev_available_funds,
            time_stamp = EXCLUDED.time_stamp,
            created_on = EXCLUDED.created_on,
            modified_on = EXCLUDED.modified_on,
            account_currency = EXCLUDED.account_currency,
            account_is_closed = EXCLUDED.account_is_closed
        WHERE EXCLUDED.modified_on IS NOT NULL
          AND (bank_accounts.modified_on IS NULL OR EXCLUDED.modified_on > bank_accounts.modified_on)
    """

    execute_batch(cursor, sql, rows, page_size=200)
    return len(rows)


def reconcile_matches(cursor) -> int:
    cursor.execute(
        """
        WITH matches AS (
            SELECT i.invoice_id, t.transaction_id
            FROM invoices i
            JOIN transactions t
              ON i.total_amount = ABS(t.amount)
             AND t.operation_date BETWEEN (i.date - INTERVAL '7 days')
                                      AND (i.date + INTERVAL '7 days')
            WHERE i.status = 'PENDING'
              AND t.reconciliation_status = 'UNMATCHED'
        ), inserted AS (
            INSERT INTO reconciliation_log (invoice_id, transaction_id, match_method, matched_at)
            SELECT invoice_id, transaction_id, 'amount_date', NOW()
            FROM matches
            RETURNING invoice_id, transaction_id
        )
        UPDATE invoices i
        SET status = 'MATCHED'
        FROM inserted ins
        WHERE i.invoice_id = ins.invoice_id
        """
    )

    cursor.execute(
        """
        UPDATE transactions t
        SET reconciliation_status = 'MATCHED'
        FROM reconciliation_log r
        WHERE t.transaction_id = r.transaction_id
          AND r.matched_at::date = CURRENT_DATE
        """
    )

    return cursor.rowcount


def update_sync_state(cursor, tenant_id: str, last_id: int, last_date: Optional[datetime]) -> None:
    cursor.execute(
        """
        INSERT INTO sync_state (tenant_id, last_processed_id, last_processed_date, last_sync_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (tenant_id) DO UPDATE
        SET last_processed_id = EXCLUDED.last_processed_id,
            last_processed_date = EXCLUDED.last_processed_date,
            last_sync_at = NOW()
        """,
        (tenant_id, last_id, last_date),
    )


def run_sync(tenant_id: str, api_url: str, bank_account_api_url: Optional[str] = None) -> Dict[str, Any]:
    """Run a full sync cycle with state machine, incremental fetch, and batch checkpoints."""
    config = load_config()
    connection = None
    cursor = None
    total_tx = 0
    total_accounts = 0

    try:
        connection = get_db_connection(config)
        cursor = connection.cursor()

        # Ensure schema is up to date (idempotent DDL)
        ensure_sync_state_columns(cursor)
        ensure_transaction_hash_column(cursor)
        connection.commit()

        # ── State machine: idle → syncing ──
        mark_sync_started(cursor, tenant_id)
        connection.commit()

        # ── Sync bank accounts ──
        if bank_account_api_url:
            accounts = fetch_bank_accounts(bank_account_api_url, config.get("api_key"))
            total_accounts = upsert_bank_accounts(cursor, accounts)
            connection.commit()

        # ── Incremental sync: use last_processed_date as cursor ──
        last_id = fetch_last_processed_id(cursor, tenant_id)
        cursor.execute(
            "SELECT last_processed_date FROM sync_state WHERE tenant_id = %s",
            (tenant_id,),
        )
        row = cursor.fetchone()
        last_date = row[0] if row and row[0] else None

        max_id = 0
        max_date = None
        page = 1
        page_size = config["page_size"]
        last_seen_id = last_id

        while True:
            transactions = fetch_transactions(
                api_url, page, page_size, config.get("api_key"),
                modified_from=last_date,
            )
            if not transactions:
                break

            new_transactions = [
                item for item in transactions if (item.get("transactionId") or 0) > last_id
            ]
            batch_max_id, batch_max_date = upsert_transactions(cursor, new_transactions)
            total_tx += len(new_transactions)

            # ── Batch checkpoint: commit after each page ──
            if batch_max_id > 0:
                update_sync_state(cursor, tenant_id, max(max_id, batch_max_id),
                                  batch_max_date if batch_max_date and (max_date is None or batch_max_date > max_date) else max_date)
            connection.commit()

            page += 1

            if batch_max_id <= last_seen_id:
                break

            last_seen_id = batch_max_id

            if batch_max_id > max_id:
                max_id = batch_max_id
            if batch_max_date and (max_date is None or batch_max_date > max_date):
                max_date = batch_max_date

        reconcile_matches(cursor)

        if max_id > 0:
            update_sync_state(cursor, tenant_id, max_id, max_date)

        # ── State machine: syncing → success ──
        mark_sync_success(cursor, tenant_id, total_tx, total_accounts)
        connection.commit()

        return {
            "status": "success",
            "transactions_synced": total_tx,
            "accounts_synced": total_accounts,
            "max_transaction_id": max_id,
        }

    except Exception as exc:
        if connection:
            try:
                cursor_err = connection.cursor()
                ensure_sync_state_columns(cursor_err)
                mark_sync_failed(cursor_err, tenant_id, str(exc)[:500])
                connection.commit()
            except Exception:
                connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync transactions and reconcile invoices.")
    parser.add_argument("--tenant-id", required=True, help="Tenant identifier for sync_state.")
    parser.add_argument("--api-url", required=True, help="Transactions API base URL.")
    parser.add_argument("--bank-account-api-url", help="Bank accounts API base URL.")
    args = parser.parse_args()

    run_sync(args.tenant_id, args.api_url, args.bank_account_api_url)


if __name__ == "__main__":
    main()
