ALTER TABLE bills
    ADD COLUMN IF NOT EXISTS processing_idempotency_key VARCHAR(128);