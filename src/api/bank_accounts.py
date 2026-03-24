"""Bank account API endpoints."""

import os
from typing import List

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["bank-accounts"])


def _get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT", "5432"),
    )


@router.get("/bank-accounts")
async def list_bank_accounts() -> List[dict]:
    connection = _get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT account_id, account_name, account_number, account_provider_id,
                   account_group_id, account_balance, account_available_funds,
                   account_prev_balance, account_prev_available_funds, time_stamp,
                   created_on, modified_on, account_currency, account_is_closed
            FROM bank_accounts
            ORDER BY account_id
            """
        )
        return cursor.fetchall()
    finally:
        connection.close()


@router.get("/bank-accounts/{account_id}")
async def get_bank_account(account_id: int) -> dict:
    connection = _get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            """
            SELECT account_id, account_name, account_number, account_provider_id,
                   account_group_id, account_balance, account_available_funds,
                   account_prev_balance, account_prev_available_funds, time_stamp,
                   created_on, modified_on, account_currency, account_is_closed
            FROM bank_accounts
            WHERE account_id = %s
            """,
            (account_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Bank account not found")
        return row
    finally:
        connection.close()
