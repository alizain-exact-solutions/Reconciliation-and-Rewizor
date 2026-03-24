"""Reconciled export endpoints (XLSX/PDF)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from src.services.reporting.reconciled_export_service import (
    export_reconciled_pdf,
    export_reconciled_xlsx,
)

router = APIRouter(tags=["reconciled-exports"])


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}") from exc


@router.get("/exports/reconciled.xlsx")
async def export_reconciled_xlsx_api(
    start_date: Optional[str] = Query(None, description="ISO start date"),
    end_date: Optional[str] = Query(None, description="ISO end date"),
    account_id: Optional[int] = Query(None, description="Account filter"),
):
    result = export_reconciled_xlsx(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        account_id=account_id,
    )
    if result["count"] == 0:
        raise HTTPException(status_code=404, detail="No reconciled data for export")

    return Response(
        content=result["xlsx_bytes"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
        },
    )


@router.get("/exports/reconciled.pdf")
async def export_reconciled_pdf_api(
    start_date: Optional[str] = Query(None, description="ISO start date"),
    end_date: Optional[str] = Query(None, description="ISO end date"),
    account_id: Optional[int] = Query(None, description="Account filter"),
):
    result = export_reconciled_pdf(
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        account_id=account_id,
    )
    if result["count"] == 0:
        raise HTTPException(status_code=404, detail="No reconciled data for export")

    return Response(
        content=result["pdf_bytes"],
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
        },
    )
