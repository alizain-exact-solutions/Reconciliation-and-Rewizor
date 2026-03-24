CREATE TABLE IF NOT EXISTS sync_state (
    tenant_id TEXT PRIMARY KEY,
    last_processed_id BIGINT,
    last_processed_date TIMESTAMP,
    last_sync_at TIMESTAMP,
    -- State machine
    sync_status TEXT DEFAULT 'idle',              -- idle | syncing | success | failed
    last_sync_started_at TIMESTAMP,
    -- Failure tracking
    consecutive_failures INT DEFAULT 0,
    total_failures INT DEFAULT 0,
    last_error TEXT,
    last_success_at TIMESTAMP,
    alert_level TEXT DEFAULT 'none',              -- none | warning | critical
    -- Stats
    transactions_synced INT DEFAULT 0,
    accounts_synced INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id SERIAL PRIMARY KEY,
    invoice_number TEXT,
    total_amount DECIMAL,
    currency TEXT,
    vat_amount DECIMAL,
    gross_amount DECIMAL,
    net_amount DECIMAL,
    date DATE,
    vendor TEXT,
    customer TEXT,
    status TEXT DEFAULT 'PENDING',
    payment_status TEXT DEFAULT 'UNPAID'
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    account_id BIGINT PRIMARY KEY,
    account_name TEXT,
    account_number TEXT,
    account_provider_id BIGINT,
    account_group_id BIGINT,
    account_balance DECIMAL,
    account_available_funds DECIMAL,
    account_prev_balance DECIMAL,
    account_prev_available_funds DECIMAL,
    time_stamp TEXT,
    created_on TIMESTAMP,
    modified_on TIMESTAMP,
    account_currency TEXT,
    account_is_closed BOOLEAN
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id BIGINT PRIMARY KEY,
    account_id BIGINT REFERENCES bank_accounts(account_id),
    amount DECIMAL,
    ref_number TEXT,
    operation_date TIMESTAMP,
    booking_date TIMESTAMP,
    description TEXT,
    partner_name TEXT,
    payment_details TEXT,
    modified_on TIMESTAMP,
    reconciliation_status TEXT DEFAULT 'UNMATCHED',
    transaction_hash TEXT UNIQUE
);

-- Fallback duplicate detection: (account_id + amount + operation_date + ref_number)
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_dedup_fallback
    ON transactions (account_id, amount, operation_date, ref_number)
    WHERE ref_number IS NOT NULL;

CREATE TABLE IF NOT EXISTS reconciliation_log (
    reconciliation_id SERIAL PRIMARY KEY,
    invoice_id INT REFERENCES invoices(invoice_id),
    transaction_id BIGINT REFERENCES transactions(transaction_id),
    match_method TEXT,
    matched_at TIMESTAMP
);
