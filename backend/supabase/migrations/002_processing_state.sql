ALTER TABLE payment_approvals
    ADD COLUMN IF NOT EXISTS processing_status VARCHAR(20) NOT NULL DEFAULT 'idle';

ALTER TABLE payment_approvals
    ADD COLUMN IF NOT EXISTS processing_message TEXT;

ALTER TABLE payment_approvals
    DROP CONSTRAINT IF EXISTS payment_approvals_processing_status_check;

ALTER TABLE payment_approvals
    ADD CONSTRAINT payment_approvals_processing_status_check
    CHECK (processing_status IN ('idle', 'processing', 'needs_review', 'blocked', 'paid', 'failed', 'cancelled'));

ALTER TABLE bills
    DROP CONSTRAINT IF EXISTS bills_status_check;

ALTER TABLE bills
    ADD CONSTRAINT bills_status_check
    CHECK (status IN ('received', 'awaiting_approval', 'processing', 'needs_review', 'paid', 'blocked', 'failed', 'cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_attempt_household_idempotency_idx
    ON payment_attempts (household_id, idempotency_key);