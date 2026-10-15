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