"""Reconciled data export (XLSX and PDF)."""

import io
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from src.repositories.reconciliation_repo import get_reconciled_pairs
from src.services.transactions.transaction_categorizer import categorize_transaction

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


def _vat_exclusion_reason(categories: List[str]) -> str:
    return ", ".join(sorted(categories)) if categories else ""


def _prepare_rows(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    prepared: List[Dict[str, Any]] = []
    total_gross = 0.0
    total_vat = 0.0

    for row in rows:
        categories = list(categorize_transaction(row))
        vat_excluded = bool(categories)
        gross = float(row.get("gross_amount") or 0)
        vat = float(row.get("vat_amount") or 0)

        total_gross += gross
        if not vat_excluded:
            total_vat += vat

        prepared.append(
            {
                **row,
                "vat_excluded": vat_excluded,
                "vat_exclusion_reason": _vat_exclusion_reason(categories),
            }
        )

    summary = {
        "count": len(prepared),
        "total_gross": total_gross,
        "total_vat": total_vat,
    }
    return prepared, summary


def export_reconciled_xlsx(
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    account_id: Optional[int] = None,
) -> Dict[str, Any]:
    connection = _get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        rows = get_reconciled_pairs(
            cursor,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
        )
    finally:
        cursor.close()
        connection.close()

    prepared, summary = _prepare_rows(rows)

    wb = Workbook()
    ws = wb.active
    ws.title = "Reconciled"

    headers = [
        "reconciliation_id",
        "matched_at",
        "match_method",
        "invoice_id",
        "invoice_number",
        "vendor",
        "invoice_date",
        "gross_amount",
        "net_amount",
        "vat_amount",
        "currency",
        "transaction_id",
        "account_id",
        "amount",
        "operation_date",
        "booking_date",
        "description",
        "partner_name",
        "ref_number",
        "payment_details",
        "vat_excluded",
        "vat_exclusion_reason",
    ]

    ws.append(headers)
    for row in prepared:
        ws.append([row.get(h) for h in headers])

    # Summary sheet
    summary_ws = wb.create_sheet("Summary")
    summary_ws.append(["count", summary["count"]])
    summary_ws.append(["total_gross", summary["total_gross"]])
    summary_ws.append(["total_vat", summary["total_vat"]])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return {
        "count": summary["count"],
        "xlsx_bytes": output.getvalue(),
        "filename": "reconciled_export.xlsx",
    }


def export_reconciled_pdf(
    *,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    account_id: Optional[int] = None,
) -> Dict[str, Any]:
    connection = _get_db_connection()
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        rows = get_reconciled_pairs(
            cursor,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
        )
    finally:
        cursor.close()
        connection.close()

    prepared, summary = _prepare_rows(rows)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    styles = getSampleStyleSheet()

    elements: List[Any] = []
    elements.append(Paragraph("Reconciled Transactions Report", styles["Title"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Total records: {summary['count']}", styles["Normal"]))
    elements.append(Paragraph(f"Total gross: {summary['total_gross']:.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Total VAT (excludes non-VAT items): {summary['total_vat']:.2f}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    table_data = [
        [
            "matched_at",
            "invoice_number",
            "vendor",
            "gross_amount",
            "vat_amount",
            "transaction_id",
            "amount",
            "operation_date",
            "vat_excluded",
        ]
    ]

    for row in prepared:
        table_data.append(
            [
                str(row.get("matched_at") or ""),
                row.get("invoice_number"),
                row.get("vendor"),
                row.get("gross_amount"),
                row.get("vat_amount"),
                row.get("transaction_id"),
                row.get("amount"),
                str(row.get("operation_date") or ""),
                "yes" if row.get("vat_excluded") else "no",
            ]
        )

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]
        )
    )

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return {
        "count": summary["count"],
        "pdf_bytes": buffer.getvalue(),
        "filename": "reconciled_export.pdf",
    }
