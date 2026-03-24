"""FastAPI application entry point."""

import logging
import os

from fastapi import FastAPI
from dotenv import load_dotenv

from src.api.bank_accounts import router as bank_accounts_router
from src.api.invoices import router as invoices_router
from src.api.reports import router as rewizor_router
from src.api.sync_dashboard import router as sync_dashboard_router
from src.api.missing_invoices import router as missing_invoices_router
from src.api.reconciled_exports import router as reconciled_exports_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="ExactFlow Digital Finance API",
    version="1.0.0",
    description="Invoice processing, OCR extraction, and bank reconciliation.",
)

app.include_router(invoices_router, prefix="/api/v1")
app.include_router(rewizor_router, prefix="/api/v1/rewizor")
app.include_router(bank_accounts_router, prefix="/api/v1")
app.include_router(sync_dashboard_router, prefix="/api/v1")
app.include_router(missing_invoices_router, prefix="/api/v1")
app.include_router(reconciled_exports_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
