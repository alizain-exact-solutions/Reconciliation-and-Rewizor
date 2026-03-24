# ExactFlow Finance Module — Project Structure

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend Framework | FastAPI (async, OpenAPI docs out of the box) |
| ORM / DB | SQLAlchemy 2.0 + Alembic migrations, PostgreSQL |
| Task Queue | Celery + Redis (OCR, NBP sync, reconciliation jobs) |
| OCR | Tesseract / Google Vision API / fallback to Claude API |
| Storage | Local filesystem + Google Cloud Storage (dual write) |
| Auth | JWT (prepared for frontend, used by API consumers now) |
| Testing | pytest + pytest-asyncio + factory_boy |
| Containerization | Docker + docker-compose |

---

## Root Layout

```
exactflow-finance/
│
├── docker/                          # Container definitions
│   ├── Dockerfile.api               # FastAPI app image
│   ├── Dockerfile.worker            # Celery worker image
│   └── docker-compose.yml           # Full local stack (db, redis, api, worker, minio)
│
├── alembic/                         # DB migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
│
├── src/                             # ── APPLICATION SOURCE ──
│   │
│   ├── config/                      # App-wide configuration
│   │   ├── __init__.py
│   │   ├── settings.py              # Pydantic Settings (env-driven)
│   │   ├── constants.py             # Business constants (VAT rates, currency codes, excluded tx types)
│   │   └── logging.py               # Structured logging setup
│   │
│   ├── core/                        # Cross-cutting concerns (framework-agnostic)
│   │   ├── __init__.py
│   │   ├── exceptions.py            # Domain exceptions (InvoiceNotFound, ReconciliationError, etc.)
│   │   ├── enums.py                 # InvoiceCategory, TransactionType, ReconciliationStatus, etc.
│   │   ├── types.py                 # Custom type aliases (Money, TaxId, etc.)
│   │   └── event_bus.py             # Simple domain event dispatcher
│   │
│   ├── models/                      # SQLAlchemy ORM models (DB layer)
│   │   ├── __init__.py
│   │   ├── base.py                  # DeclarativeBase, mixins (timestamps, soft-delete)
│   │   ├── invoice.py               # Invoice, InvoiceLineItem
│   │   ├── supplier.py              # Supplier
│   │   ├── bank_statement.py        # BankStatement, BankTransaction
│   │   ├── reconciliation.py        # ReconciliationRecord (invoice ↔ transaction link)
│   │   ├── exchange_rate.py         # NBP exchange rate cache
│   │   ├── document.py              # StoredDocument (file metadata, GCS path, local path)
│   │   └── audit_log.py             # AuditLog (who changed what, when)
│   │
│   ├── schemas/                     # Pydantic v2 schemas (API contracts)
│   │   ├── __init__.py
│   │   ├── invoice.py               # InvoiceCreate, InvoiceRead, InvoiceUpdate, InvoiceFilter
│   │   ├── supplier.py              # SupplierRead, SupplierCreate
│   │   ├── bank.py                  # BankStatementUpload, TransactionRead, TransactionFilter
│   │   ├── reconciliation.py        # ReconciliationResult, MissingInvoiceAlert
│   │   ├── exchange_rate.py         # ExchangeRateRead
│   │   ├── reports.py               # CostReport, VATReport, ReconciliationReport
│   │   └── common.py                # PaginatedResponse, ErrorResponse, FileUploadMeta
│   │
│   ├── repositories/               # Data access layer (queries, no business logic)
│   │   ├── __init__.py
│   │   ├── base.py                  # BaseRepository[T] — generic CRUD
│   │   ├── invoice_repo.py          # InvoiceRepository (filters, aggregations)
│   │   ├── supplier_repo.py         # SupplierRepository
│   │   ├── bank_repo.py             # BankStatementRepository, BankTransactionRepository
│   │   ├── reconciliation_repo.py   # ReconciliationRepository
│   │   └── exchange_rate_repo.py    # ExchangeRateRepository (cache lookups)
│   │
│   ├── services/                    # ── BUSINESS LOGIC LAYER ──
│   │   ├── __init__.py
│   │   │
│   │   ├── invoice/                 # Invoice & Cost Management domain
│   │   │   ├── __init__.py
│   │   │   ├── invoice_service.py   # Create, update, list, categorize invoices
│   │   │   ├── ocr_service.py       # PDF/image → structured invoice data
│   │   │   ├── ocr_strategies/      # Strategy pattern for OCR providers
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py          # OCRStrategy ABC
│   │   │   │   ├── tesseract.py     # Local Tesseract OCR
│   │   │   │   ├── google_vision.py # Google Cloud Vision
│   │   │   │   └── claude_ocr.py    # Claude API for invoice parsing
│   │   │   ├── currency_service.py  # NBP rate fetch, foreign → PLN conversion
│   │   │   └── categorizer.py       # Rule engine: Operating Cost vs Inventory Purchase
│   │   │
│   │   ├── bank/                    # Bank Reconciliation domain
│   │   │   ├── __init__.py
│   │   │   ├── statement_service.py # Import CSV/MT940, parse transactions
│   │   │   ├── parsers/             # Statement format parsers
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py          # StatementParser ABC
│   │   │   │   ├── csv_parser.py    # Generic CSV bank statement
│   │   │   │   └── mt940_parser.py  # SWIFT MT940 format
│   │   │   ├── reconciliation_service.py  # Match transactions ↔ invoices
│   │   │   ├── matching_engine.py   # Matching algorithms (amount, supplier, invoice #)
│   │   │   └── exclusion_rules.py   # FX conversions, fees, ZUS, salaries, tax — skip from VAT
│   │   │
│   │   ├── vat/                     # VAT calculation domain
│   │   │   ├── __init__.py
│   │   │   ├── vat_service.py       # Input VAT aggregation, validation
│   │   │   └── vat_rules.py         # Polish VAT rate logic (23%, 8%, 5%, 0%, exempt)
│   │   │
│   │   ├── reporting/               # Report generation domain
│   │   │   ├── __init__.py
│   │   │   ├── report_service.py    # Orchestrates report generation
│   │   │   ├── cost_report.py       # Operating cost report (excl. inventory)
│   │   │   ├── vat_report.py        # VAT summary for filing
│   │   │   └── reconciliation_report.py  # Matched/unmatched/missing invoice report
│   │   │
│   │   └── storage/                 # Document storage domain
│   │       ├── __init__.py
│   │       ├── storage_service.py   # Upload orchestrator (local + GCS dual-write)
│   │       ├── local_storage.py     # Filesystem storage
│   │       └── gcs_storage.py       # Google Cloud Storage client
│   │
│   ├── api/                         # ── HTTP LAYER (FastAPI) ──
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory, middleware, lifespan
│   │   ├── deps.py                  # Dependency injection (get_db, get_current_user, get_service)
│   │   │
│   │   ├── v1/                      # API version 1
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # Aggregates all v1 routers → /api/v1
│   │   │   ├── invoices.py          # POST /invoices/upload, GET /invoices, PATCH /invoices/{id}
│   │   │   ├── suppliers.py         # CRUD /suppliers
│   │   │   ├── bank.py              # POST /bank/upload, GET /bank/transactions
│   │   │   ├── reconciliation.py    # POST /reconciliation/run, GET /reconciliation/results
│   │   │   ├── reports.py           # GET /reports/costs, /reports/vat, /reports/reconciliation
│   │   │   ├── exchange_rates.py    # GET /exchange-rates (manual lookup)
│   │   │   └── health.py            # GET /health, GET /ready
│   │   │
│   │   └── middleware/
│   │       ├── __init__.py
│   │       ├── error_handler.py     # Global exception → JSON error response
│   │       ├── request_id.py        # X-Request-ID injection
│   │       └── timing.py            # Request duration logging
│   │
│   ├── workers/                     # ── ASYNC TASK LAYER (Celery) ──
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery application config
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── ocr_task.py          # Async invoice OCR processing
│   │   │   ├── nbp_sync_task.py     # Daily NBP exchange rate sync
│   │   │   ├── reconciliation_task.py  # Auto-reconciliation batch job
│   │   │   ├── report_task.py       # Heavy report generation (Excel/PDF)
│   │   │   └── gcs_upload_task.py   # Async GCS backup upload
│   │   └── schedules.py             # Celery Beat periodic task schedule
│   │
│   └── integrations/                # ── EXTERNAL SYSTEM ADAPTERS ──
│       ├── __init__.py
│       ├── nbp/                     # National Bank of Poland API
│       │   ├── __init__.py
│       │   ├── client.py            # HTTP client for NBP API (api.nbp.pl)
│       │   └── schemas.py           # NBP response models
│       ├── ksef/                    # KSeF e-invoice integration (future)
│       │   ├── __init__.py
│       │   ├── client.py            # KSeF API client
│       │   └── schemas.py           # KSeF XML/JSON models
│       └── gcs/                     # Google Cloud Storage
│           ├── __init__.py
│           └── client.py            # GCS bucket operations
│
├── tests/                           # ── TEST SUITE ──
│   ├── conftest.py                  # Fixtures: db session, test client, factories
│   ├── factories/                   # factory_boy model factories
│   │   ├── __init__.py
│   │   ├── invoice_factory.py
│   │   ├── transaction_factory.py
│   │   └── supplier_factory.py
│   ├── unit/                        # Pure logic tests (no DB, no network)
│   │   ├── test_matching_engine.py
│   │   ├── test_exclusion_rules.py
│   │   ├── test_vat_rules.py
│   │   ├── test_currency_conversion.py
│   │   ├── test_mt940_parser.py
│   │   └── test_categorizer.py
│   ├── integration/                 # Tests with DB / external services
│   │   ├── test_invoice_service.py
│   │   ├── test_reconciliation_service.py
│   │   ├── test_nbp_client.py
│   │   └── test_storage_service.py
│   └── e2e/                         # Full API flow tests
│       ├── test_invoice_flow.py     # Upload → OCR → categorize → store
│       ├── test_reconciliation_flow.py  # Upload statement → match → report
│       └── test_report_flow.py
│
├── scripts/                         # Utility scripts
│   ├── seed_data.py                 # Seed DB with sample invoices/transactions
│   ├── sync_nbp_rates.py           # One-off NBP rate backfill
│   └── migrate.sh                   # Run alembic migrations
│
├── docs/                            # Documentation
│   ├── architecture.md              # System architecture overview
│   ├── api.md                       # API usage guide (supplements OpenAPI)
│   ├── deployment.md                # AWS deployment guide
│   └── decisions/                   # Architecture Decision Records
│       ├── 001-why-fastapi.md
│       ├── 002-ocr-strategy.md
│       └── 003-dual-storage.md
│
├── frontend/                        # ── FRONTEND (Future) ──
│   ├── README.md                    # "Next.js 15 + MUI — coming soon"
│   └── .gitkeep
│
├── .env.example                     # Environment variable template
├── .gitignore
├── pyproject.toml                   # Project metadata, dependencies, tool config
├── alembic.ini                      # Alembic configuration
├── Makefile                         # dev, test, lint, migrate, docker shortcuts
└── README.md                        # Project overview and quickstart
```

---

## Key Architectural Decisions

### 1. Layered Architecture (not MVC)

```
API (routers)  →  Services (business logic)  →  Repositories (data access)  →  Models (ORM)
     ↕                    ↕                            ↕
  Schemas            Integrations                  Database
 (Pydantic)        (NBP, GCS, KSeF)             (PostgreSQL)
```

Each layer has a single responsibility. Services never touch the HTTP layer directly. Repositories never contain business rules. This keeps the codebase testable and swappable.

### 2. Strategy Pattern for OCR & Parsers

OCR providers and bank statement formats are pluggable. Adding a new OCR engine or a new bank format means adding one file — no changes to existing code.

### 3. Dual-Write Storage

Every uploaded document is stored locally **and** pushed to GCS asynchronously via Celery. Local storage serves the API; GCS serves as backup and audit archive.

### 4. Separation of Invoice Categories

Operating Cost invoices flow into cost reports and VAT calculations. Inventory Purchase invoices are stored but excluded from cost reports. This distinction is enforced at the service layer, not in queries scattered across the codebase.

### 5. Explicit VAT Exclusion Rules

The `exclusion_rules.py` module codifies exactly which transaction types are excluded from VAT calculations (FX conversions, bank fees, ZUS, salaries, internal transfers, customer payments). These rules are unit-tested independently.

---

## Database Schema Overview

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Supplier   │────<│     Invoice      │────<│ InvoiceLineItem │
└──────────────┘     │                  │     └─────────────────┘
                     │  invoice_number  │
                     │  date            │
                     │  net_amount      │
                     │  vat_amount      │
                     │  gross_amount    │
                     │  currency        │
                     │  pln_net         │
                     │  pln_vat         │
                     │  pln_gross       │
                     │  nbp_rate        │
                     │  nbp_rate_date   │
                     │  category (enum) │
                     │  status          │
                     └────────┬─────────┘
                              │
                     ┌────────┴─────────┐
                     │ Reconciliation   │
                     │    Record        │
                     │  match_score     │
                     │  match_method    │
                     │  status          │
                     └────────┬─────────┘
                              │
                     ┌────────┴─────────┐
                     │ BankTransaction  │────<┌──────────────────┐
                     │  date            │     │  BankStatement   │
                     │  amount          │     │  (file metadata) │
                     │  counterparty    │     └──────────────────┘
                     │  reference       │
                     │  tx_type (enum)  │
                     │  excluded (bool) │
                     └──────────────────┘

┌──────────────────┐     ┌──────────────────┐
│  ExchangeRate    │     │ StoredDocument   │
│  currency        │     │  original_name   │
│  rate            │     │  local_path      │
│  effective_date  │     │  gcs_path        │
│  table_number    │     │  mime_type       │
└──────────────────┘     │  linked_entity   │
                         └──────────────────┘
```

---

## Environment Variables (.env.example)

```env
# ── Database ──
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/exactflow_finance

# ── Redis ──
REDIS_URL=redis://localhost:6379/0

# ── OCR ──
OCR_PROVIDER=tesseract                  # tesseract | google_vision | claude
GOOGLE_VISION_CREDENTIALS=/path/to/sa.json
ANTHROPIC_API_KEY=sk-ant-...

# ── Google Cloud Storage ──
GCS_BUCKET=exactflow-finance-docs
GCS_CREDENTIALS=/path/to/sa.json

# ── NBP ──
NBP_API_BASE_URL=https://api.nbp.pl/api

# ── KSeF (future) ──
KSEF_ENV=test                           # test | prod
KSEF_TOKEN=...

# ── App ──
SECRET_KEY=change-me
ALLOWED_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```

---

## Makefile Shortcuts

```makefile
dev:             ## Start API with hot-reload
	uvicorn src.api.main:app --reload --port 8000

worker:          ## Start Celery worker
	celery -A src.workers.celery_app worker -l info

beat:            ## Start Celery Beat scheduler
	celery -A src.workers.celery_app beat -l info

migrate:         ## Run DB migrations
	alembic upgrade head

migration:       ## Create new migration
	alembic revision --autogenerate -m "$(msg)"

test:            ## Run full test suite
	pytest tests/ -v --tb=short

test-unit:       ## Run unit tests only
	pytest tests/unit/ -v

lint:            ## Lint + format
	ruff check src/ tests/ --fix
	ruff format src/ tests/

docker-up:       ## Start full stack
	docker compose -f docker/docker-compose.yml up -d

docker-down:     ## Stop full stack
	docker compose -f docker/docker-compose.yml down
```
