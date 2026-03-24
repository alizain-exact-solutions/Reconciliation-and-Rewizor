"""
Rewizor GT export service – orchestrator.

Two main workflows:

1. **OCR + Export**  (``process_and_export``)
   Upload PDF → Rewizor OCR → EPP file bytes

2. **DB Export**  (``export_from_db``)
   Fetch invoices already in the database → EPP file bytes
"""

import logging
import os
from typing import Any, Dict, List, Optional

import psycopg2
from dotenv import load_dotenv

from src.integrations.rewizor.constants import DOC_TYPE_PURCHASE_INVOICE
from src.integrations.rewizor.epp_writer import generate_epp_bytes
from src.integrations.rewizor.mapper import map_invoice_to_epp
from src.integrations.rewizor.schemas import EPPDocument, EPPInfo
from src.services.invoice.rewizor_ocr import RewizorOCRService

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


def _build_epp_info() -> EPPInfo:
    """Read sender / accounting-office details from environment."""
    return EPPInfo(
        generator_name=os.getenv("EPP_SENDER_NAME", "ExactFlow Finance"),
        generator_nip=os.getenv("EPP_SENDER_NIP", ""),
        generator_city=os.getenv("EPP_SENDER_CITY", ""),
        company_name=os.getenv("EPP_COMPANY_NAME", ""),
        company_nip=os.getenv("EPP_COMPANY_NIP", ""),  # with country prefix, e.g. "PL5252704499"
    )


# ── Workflow 1: OCR + immediate export ───────────────────────────────────────

def process_and_export(
    file_path: str,
) -> Dict[str, Any]:
    """Run Rewizor OCR on *file_path* and return EPP bytes + extracted data.

    The document type (FZ, FS, KZ, KS, FZK, FSK, KZK, KSK, WB, RK, PK, DE)
    is auto-detected by the OCR from the document content.

    Returns::

        {
            "invoice_data": { … },          # raw OCR output (normalised)
            "epp_bytes": b"…",              # Windows-1250 encoded EPP content
            "epp_filename": "FV_001_2026.epp",
            "doc_type": "FS",               # detected document type
        }
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Invoice file not found: {file_path}")

    ocr = RewizorOCRService()
    invoice_data = ocr.extract(file_path)

    # doc_type is auto-detected by mapper from invoice_data["doc_type"]
    epp_doc = map_invoice_to_epp(invoice_data)
    info = _build_epp_info()
    epp_bytes = generate_epp_bytes(info, [epp_doc])

    filename = _safe_filename(invoice_data.get("invoice_number") or "export")

    logger.info(
        "Rewizor export: generated %s (%d bytes, type=%s)",
        filename, len(epp_bytes), invoice_data.get("doc_type"),
    )
    return {
        "invoice_data": invoice_data,
        "epp_bytes": epp_bytes,
        "epp_filename": filename,
        "doc_type": invoice_data.get("doc_type", "FZ"),
    }


# ── Workflow 2: batch export from DB ─────────────────────────────────────────

def export_from_db(
    *,
    invoice_ids: Optional[List[int]] = None,
    status: str = "PENDING",
    doc_type: str = DOC_TYPE_PURCHASE_INVOICE,
) -> Dict[str, Any]:
    """Fetch invoices from the database and generate a batch EPP file.

    Args:
        invoice_ids: Explicit list of ``invoice_id`` values.  When *None*,
                     all invoices matching *status* are exported.
        status: Invoice status filter (used when *invoice_ids* is None).
        doc_type: Document type written into [NAGLOWEK].

    Returns::

        {
            "count": int,
            "epp_bytes": b"…",
            "epp_filename": "rewizor_export.epp",
        }
    """
    connection = _get_db_connection()
    try:
        cursor = connection.cursor()

        if invoice_ids:
            cursor.execute(
                """
                SELECT invoice_id, invoice_number, total_amount, currency,
                       vat_amount, gross_amount, net_amount, date,
                       vendor, customer
                FROM invoices
                WHERE invoice_id = ANY(%s)
                ORDER BY invoice_id
                """,
                (invoice_ids,),
            )
        else:
            cursor.execute(
                """
                SELECT invoice_id, invoice_number, total_amount, currency,
                       vat_amount, gross_amount, net_amount, date,
                       vendor, customer
                FROM invoices
                WHERE status = %s
                ORDER BY invoice_id
                """,
                (status,),
            )

        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()

    if not rows:
        logger.warning("Rewizor export: no invoices found")
        return {"count": 0, "epp_bytes": b"", "epp_filename": ""}

    documents: List[EPPDocument] = [
        map_invoice_to_epp(row, doc_type=doc_type) for row in rows
    ]

    info = _build_epp_info()
    epp_bytes = generate_epp_bytes(info, documents)
    filename = _safe_filename("rewizor_export")

    logger.info(
        "Rewizor DB export: %d invoice(s), %d bytes", len(documents), len(epp_bytes)
    )
    return {
        "count": len(documents),
        "epp_bytes": epp_bytes,
        "epp_filename": filename,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_filename(base: str) -> str:
    """Sanitise an invoice number into a valid .epp filename."""
    cleaned = base.replace("/", "_").replace("\\", "_").replace(" ", "_")
    # Drop any characters that are not alphanumeric, underscore, or hyphen
    cleaned = "".join(c for c in cleaned if c.isalnum() or c in ("_", "-"))
    return (cleaned or "export") + ".epp"
