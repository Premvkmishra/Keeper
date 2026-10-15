-- Keeper Canonical Seed Data
-- Creates default household, policy, trusted billers, and approved beneficiaries

INSERT INTO households (id, name, currency)
VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Senior Household', 'INR')
ON CONFLICT (id) DO NOTHING;

INSERT INTO household_policies (household_id, auto_pay_limit, currency, approval_ttl_minutes, version, updated_by_name)
VALUES ('00000000-0000-0000-0000-000000000001', 10000.00, 'INR', 1440, 1, 'System Seed')
ON CONFLICT (household_id) DO NOTHING;

-- Billers
INSERT INTO trusted_billers (id, household_id, name, category, consumer_reference, status)
VALUES
    ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'City Electricity', 'electricity', 'ELEC-9988', 'active'),
    ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'Safe Insurance', 'insurance', 'INS-4421', 'active')
ON CONFLICT (id) DO NOTHING;

-- Approved Beneficiaries
INSERT INTO approved_beneficiaries (id, household_id, biller_id, display_name, account_number, account_number_masked, ifsc, status)
VALUES
    ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'City Electricity Supply', '112233440101', '••••••••0101', 'HDFC0001234', 'active'),
    ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000002', 'Safe Insurance Premium', '556677880202', '••••••••0202', 'ICIC0004321', 'active')
ON CONFLICT (id) DO NOTHING;

-- Seeded bills are pending records, not simulated payment outcomes.
INSERT INTO bills (
    id, household_id, biller_id, title, category, amount, currency, due_date,
    status, source, invoice_ref, destination_account_number,
    destination_account_number_masked, destination_ifsc, destination_matches_approved
)
VALUES
    (
        '30000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        'Sample electricity bill', 'electricity', 2400.00, 'INR', CURRENT_DATE + 14,
        'received', 'demo', 'SEED-ELEC-001', '112233440101', '••••••••0101', 'HDFC0001234', TRUE
    ),
    (
        '30000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000002',
        'Sample insurance bill', 'insurance', 48000.00, 'INR', CURRENT_DATE + 21,
        'received', 'demo', 'SEED-INS-001', '556677880202', '••••••••0202', 'ICIC0004321', TRUE
    )
ON CONFLICT (id) DO NOTHING;
