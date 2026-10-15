-- Keeper Database Schema (PostgreSQL / Supabase)
-- Authoritative schema for Keeper application state

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Households
CREATE TABLE IF NOT EXISTS households (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Household Members
CREATE TABLE IF NOT EXISTS household_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('owner', 'caregiver', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_household_member_user UNIQUE (household_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_household_members_user_id ON household_members(user_id);
CREATE INDEX IF NOT EXISTS idx_household_members_email ON household_members(email);

-- 3. Household Policies
CREATE TABLE IF NOT EXISTS household_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL UNIQUE REFERENCES households(id) ON DELETE CASCADE,
    auto_pay_limit NUMERIC(12, 2) NOT NULL DEFAULT 10000.00 CHECK (auto_pay_limit >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    approval_ttl_minutes INTEGER NOT NULL DEFAULT 1440 CHECK (approval_ttl_minutes >= 5 AND approval_ttl_minutes <= 10080),
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by_user_id UUID,
    updated_by_name TEXT
);

-- 4. Trusted Billers
CREATE TABLE IF NOT EXISTS trusted_billers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category VARCHAR(20) NOT NULL CHECK (category IN ('electricity', 'water', 'gas', 'internet', 'phone', 'insurance', 'other')),
    consumer_reference TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trusted_billers_household ON trusted_billers(household_id);

-- 5. Approved Beneficiaries
CREATE TABLE IF NOT EXISTS approved_beneficiaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    biller_id UUID NOT NULL REFERENCES trusted_billers(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    account_number TEXT NOT NULL,
    account_number_masked TEXT NOT NULL,
    ifsc VARCHAR(11) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_approved_beneficiaries_biller ON approved_beneficiaries(biller_id);
CREATE INDEX IF NOT EXISTS idx_approved_beneficiaries_lookup ON approved_beneficiaries(household_id, account_number, ifsc, status);

-- 6. Bills
CREATE TABLE IF NOT EXISTS bills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    biller_id UUID REFERENCES trusted_billers(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    category VARCHAR(20) NOT NULL CHECK (category IN ('electricity', 'water', 'gas', 'internet', 'phone', 'insurance', 'other')),
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    due_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'awaiting_approval', 'processing', 'needs_review', 'paid', 'blocked', 'failed', 'cancelled')),
    source VARCHAR(20) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'email_ingest', 'agent', 'demo')),
    invoice_ref TEXT,
    destination_account_number TEXT NOT NULL,
    destination_account_number_masked TEXT NOT NULL,
    destination_ifsc VARCHAR(11) NOT NULL,
    destination_matches_approved BOOLEAN NOT NULL DEFAULT FALSE,
    processing_idempotency_key VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_bills_household_status ON bills(household_id, status);

-- 7. Uploaded bill documents
CREATE TABLE IF NOT EXISTS bill_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    bill_id UUID NOT NULL UNIQUE REFERENCES bills(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    content BYTEA NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bill_documents_household ON bill_documents(household_id);

-- 8. Payment Approvals
CREATE TABLE IF NOT EXISTS payment_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    destination_account_number TEXT NOT NULL,
    destination_account_number_masked TEXT NOT NULL,
    destination_ifsc VARCHAR(11) NOT NULL,
    details_hash TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'invalidated', 'consumed')),
    processing_status VARCHAR(20) NOT NULL DEFAULT 'idle' CHECK (processing_status IN ('idle', 'processing', 'needs_review', 'blocked', 'paid', 'failed', 'cancelled')),
    processing_message TEXT,
    reason_code VARCHAR(40) NOT NULL DEFAULT 'amount_exceeds_limit',
    requested_by_type VARCHAR(20) NOT NULL CHECK (requested_by_type IN ('agent', 'user')),
    requested_by_user_id UUID,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ,
    decided_by_user_id UUID,
    decided_by_name TEXT,
    decision_note TEXT,
    invalidated_reason VARCHAR(40) CHECK (invalidated_reason IN ('bill_details_changed', 'beneficiary_revoked', 'biller_suspended'))
);
CREATE INDEX IF NOT EXISTS idx_approvals_bill_id ON payment_approvals(bill_id);
CREATE INDEX IF NOT EXISTS idx_approvals_household_status ON payment_approvals(household_id, status);

-- 9. Payment Attempts
CREATE TABLE IF NOT EXISTS payment_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    approval_id UUID REFERENCES payment_approvals(id) ON DELETE SET NULL,
    idempotency_key TEXT NOT NULL,
    client_reference TEXT NOT NULL UNIQUE,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    destination_account_number TEXT NOT NULL,
    destination_account_number_masked TEXT NOT NULL,
    destination_ifsc VARCHAR(11) NOT NULL,
    initiated_by_type VARCHAR(20) NOT NULL CHECK (initiated_by_type IN ('agent', 'user')),
    initiated_by_user_id UUID,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('allow', 'deny', 'require_approval')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('requires_approval', 'blocked', 'executing', 'succeeded', 'failed')),
    reason_code VARCHAR(40) NOT NULL,
    message TEXT NOT NULL,
    bank_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    latest_witness_report_id UUID
);
CREATE INDEX IF NOT EXISTS idx_attempts_household ON payment_attempts(household_id);
CREATE INDEX IF NOT EXISTS idx_attempts_bill ON payment_attempts(bill_id);
CREATE INDEX IF NOT EXISTS idx_attempts_idempotency ON payment_attempts(household_id, idempotency_key);
CREATE UNIQUE INDEX IF NOT EXISTS uq_attempt_household_idempotency_idx
    ON payment_attempts (household_id, idempotency_key);

-- 10. Security Events
CREATE TABLE IF NOT EXISTS security_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    bill_id UUID REFERENCES bills(id) ON DELETE SET NULL,
    attempt_id UUID REFERENCES payment_attempts(id) ON DELETE SET NULL,
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    actor_type VARCHAR(20) NOT NULL CHECK (actor_type IN ('user', 'agent', 'system', 'witness')),
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_security_events_household ON security_events(household_id, created_at DESC);

-- 11. Witness Reports
CREATE TABLE IF NOT EXISTS witness_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    attempt_id UUID NOT NULL REFERENCES payment_attempts(id) ON DELETE CASCADE,
    bill_id UUID NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    expected_outcome VARCHAR(30) NOT NULL CHECK (expected_outcome IN ('payment_present', 'payment_absent')),
    verdict VARCHAR(30) NOT NULL CHECK (verdict IN ('confirmed_paid', 'confirmed_no_payment', 'mismatch_detected', 'unverifiable')),
    ledger_match_count INTEGER NOT NULL DEFAULT 0,
    matched_transactions JSONB NOT NULL DEFAULT '[]'::jsonb,
    summary TEXT NOT NULL,
    ledger_source VARCHAR(30) NOT NULL DEFAULT 'mock_bank_sqlite',
    read_only BOOLEAN NOT NULL DEFAULT TRUE,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_witness_reports_attempt ON witness_reports(attempt_id);
CREATE INDEX IF NOT EXISTS idx_witness_reports_household ON witness_reports(household_id);

-- Foreign key update on payment_attempts.latest_witness_report_id
ALTER TABLE payment_attempts
    DROP CONSTRAINT IF EXISTS fk_payment_attempts_witness_report;
ALTER TABLE payment_attempts
    ADD CONSTRAINT fk_payment_attempts_witness_report
    FOREIGN KEY (latest_witness_report_id) REFERENCES witness_reports(id) ON DELETE SET NULL;

-- Helper bootstrap function for new users
CREATE OR REPLACE FUNCTION bootstrap_household(
    p_user_id UUID,
    p_user_email TEXT,
    p_display_name TEXT,
    p_household_name TEXT DEFAULT 'Family Household'
) RETURNS UUID AS $$
DECLARE
    v_household_id UUID;
    v_biller1_id UUID;
    v_biller2_id UUID;
BEGIN
    -- Check if user already belongs to a household
    SELECT household_id INTO v_household_id
    FROM household_members
    WHERE user_id = p_user_id
    LIMIT 1;

    IF v_household_id IS NOT NULL THEN
        RETURN v_household_id;
    END IF;

    -- Create household
    INSERT INTO households (id, name, currency)
    VALUES (gen_random_uuid(), p_household_name, 'INR')
    RETURNING id INTO v_household_id;

    -- Add user as owner
    INSERT INTO household_members (household_id, user_id, email, display_name, role)
    VALUES (v_household_id, p_user_id, p_user_email, p_display_name, 'owner');

    -- Create default policy
    INSERT INTO household_policies (household_id, auto_pay_limit, currency, approval_ttl_minutes, version, updated_by_name)
    VALUES (v_household_id, 10000.00, 'INR', 1440, 1, p_display_name);

    -- Seed trusted billers
    INSERT INTO trusted_billers (household_id, name, category, consumer_reference, status)
    VALUES (v_household_id, 'State Electricity Board', 'electricity', 'CONS-EL-1092', 'active')
    RETURNING id INTO v_biller1_id;

    INSERT INTO trusted_billers (household_id, name, category, consumer_reference, status)
    VALUES (v_household_id, 'SafeCare Health Insurance', 'insurance', 'POL-INS-8842', 'active')
    RETURNING id INTO v_biller2_id;

    -- Seed approved beneficiaries
    INSERT INTO approved_beneficiaries (household_id, biller_id, display_name, account_number, account_number_masked, ifsc, status)
    VALUES (v_household_id, v_biller1_id, 'State Electricity Board', '112233440101', '••••••••0101', 'HDFC0001234', 'active');

    INSERT INTO approved_beneficiaries (household_id, biller_id, display_name, account_number, account_number_masked, ifsc, status)
    VALUES (v_household_id, v_biller2_id, 'SafeCare Insurance Ltd', '556677880202', '••••••••0202', 'ICIC0004321', 'active');

    RETURN v_household_id;
END;
$$ LANGUAGE plpgsql;
