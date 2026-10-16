import uuid
import pytest
from sqlalchemy import Uuid, select
from sqlalchemy.dialects import postgresql
from backend.tests.conftest import make_auth_token
from backend.app.core.config import settings
from backend.app.models.models import Household
from backend.app.services.policy_engine import compute_details_hash

def test_household_uuid_filter_uses_postgresql_uuid_bind():
    statement = select(Household).where(Household.id == str(uuid.uuid4()))
    compiled = statement.compile(dialect=postgresql.dialect())
    bind_type = compiled.binds["id_1"].type

    assert isinstance(bind_type, Uuid)
    assert bind_type.as_uuid is False

def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "database" in data
    assert "mock_bank" in data
    assert "version" in data

def test_mock_bank_is_available_inside_backend(client):
    health = client.get("/_internal/mock-bank/health")
    assert health.status_code == 200
    assert health.json()["service"] == "mock_bank"

    unauthorized = client.post(
        "/_internal/mock-bank/bank/v1/payments",
        json={
            "client_reference": "test-reference",
            "amount": "1.00",
            "currency": "INR",
            "destination_account_number": "123456789012",
            "destination_ifsc": "HDFC0001234",
        },
    )
    assert unauthorized.status_code == 401

def test_bill_upload_persists_document_and_rejects_mismatched_signature(client, seed_data, db):
    from backend.app.models.models import BillDocument

    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    form = {
        "title": "Uploaded electricity bill",
        "category": "electricity",
        "amount": "2400.00",
        "due_date": "2026-11-10",
        "destination_account_number": "112233440101",
        "destination_ifsc": "HDFC0001234",
    }
    response = client.post(
        "/api/v1/bills/upload",
        data=form,
        files={"file": ("electricity.pdf", b"%PDF-1.4\nBill content", "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 201
    bill_id = response.json()["id"]
    document = db.query(BillDocument).filter(BillDocument.bill_id == bill_id).one()
    assert document.original_filename == "electricity.pdf"
    assert document.content.startswith(b"%PDF-")
    assert len(document.sha256) == 64

    invalid = client.post(
        "/api/v1/bills/upload",
        data={**form, "title": "Invalid upload"},
        files={"file": ("fake.pdf", b"not a PDF", "application/pdf")},
        headers=headers,
    )
    assert invalid.status_code == 415
    assert db.query(BillDocument).count() == 1

def test_unauthenticated_request(client):
    res = client.get("/api/v1/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthenticated"


def test_demo_admin_login_is_not_available(client):
    res = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert res.status_code == 404


def test_auth_fails_closed_without_jwt_secret(client, seed_data):
    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    previous_secret = settings.SUPABASE_JWT_SECRET
    settings.SUPABASE_JWT_SECRET = None
    try:
        response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        settings.SUPABASE_JWT_SECRET = previous_secret

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"

def test_user_without_household(client):
    token = make_auth_token(str(uuid.uuid4()), "stranger@test.com")
    res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    err = res.json()["error"]
    assert err["code"] == "forbidden"
    assert err["details"]["reason"] == "no_household_membership"

def test_me_and_dashboard(client, seed_data):
    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "owner@test.com"
    assert data["role"] == "owner"
    assert data["permissions"]["can_manage_policy"] is True

    dash_res = client.get("/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert dash_res.status_code == 200
    dash = dash_res.json()
    assert "counts" in dash
    assert "policy" in dash
    assert dash["policy"]["auto_pay_limit"] == "10000.00"

def test_household_isolation(client, seed_data):
    # Owner of H1 creates a bill
    h1_token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    bill_payload = {
        "title": "Private H1 Bill",
        "category": "electricity",
        "amount": "1500.00",
        "currency": "INR",
        "due_date": "2026-10-30",
        "destination_account_number": "112233440101",
        "destination_ifsc": "HDFC0001234",
    }
    create_res = client.post("/api/v1/bills", json=bill_payload, headers={"Authorization": f"Bearer {h1_token}"})
    assert create_res.status_code == 201
    bill_id = create_res.json()["id"]

    # User of H2 tries to access bill
    h2_token = make_auth_token(seed_data["h2_user_id"], "other@test.com")
    get_res = client.get(f"/api/v1/bills/{bill_id}", headers={"Authorization": f"Bearer {h2_token}"})
    assert get_res.status_code == 404

    # User of H2 tries to pay bill
    pay_res = client.post(
        f"/api/v1/bills/{bill_id}/pay",
        json={"idempotency_key": "h2-try"},
        headers={"Authorization": f"Bearer {h2_token}"},
    )
    assert pay_res.status_code == 404

def test_unapproved_beneficiary_blocked(client, seed_data):
    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    bill_payload = {
        "title": "Malicious Bill",
        "category": "electricity",
        "amount": "2400.00",
        "currency": "INR",
        "due_date": "2026-10-30",
        "destination_account_number": "999900001234",  # Not on approved list
        "destination_ifsc": "FAKE0000666",
    }
    create_res = client.post("/api/v1/bills", json=bill_payload, headers={"Authorization": f"Bearer {token}"})
    assert create_res.status_code == 201
    bill = create_res.json()
    assert bill["destination_matches_approved"] is False

    # Try to pay
    pay_res = client.post(
        f"/api/v1/bills/{bill['id']}/pay",
        json={"idempotency_key": "pay-malicious-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pay_res.status_code == 200
    outcome = pay_res.json()
    assert outcome["decision"] == "deny"
    assert outcome["reason_code"] == "beneficiary_not_approved"
    assert outcome["attempt"]["status"] == "blocked"
    assert outcome["witness_report"]["verdict"] == "confirmed_no_payment"

    # Verify security event was recorded
    sec_res = client.get(
        f"/api/v1/security-events?bill_id={bill['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sec_res.status_code == 200
    events = sec_res.json()["items"]
    assert any(e["event_type"] == "beneficiary_mismatch" for e in events)

def test_high_value_payment_requires_approval_and_resumes(client, seed_data, db, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from backend.app.models.models import PaymentAttempt, PaymentApproval, WitnessReportModel

    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    bill_payload = {
        "title": "Large Insurance Bill",
        "category": "insurance",
        "amount": "48000.00",  # Exceeds 10,000 limit
        "currency": "INR",
        "due_date": "2026-10-30",
        "destination_account_number": "112233440101",
        "destination_ifsc": "HDFC0001234",
    }
    create_res = client.post("/api/v1/bills", json=bill_payload, headers={"Authorization": f"Bearer {token}"})
    assert create_res.status_code == 201
    bill_id = create_res.json()["id"]

    # Initial pay attempt
    pay_res = client.post(
        f"/api/v1/bills/{bill_id}/pay",
        json={"idempotency_key": "pay-high-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pay_res.status_code == 200
    outcome = pay_res.json()
    assert outcome["decision"] == "require_approval"
    assert outcome["reason_code"] == "amount_exceeds_limit"
    assert outcome["approval"] is not None
    approval_id = outcome["approval"]["id"]
    details_hash = outcome["approval"]["details_hash"]

    # Human approves
    appr_res = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"details_hash": details_hash, "note": "Verified by family."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert appr_res.status_code == 200
    approval = appr_res.json()
    assert approval["status"] == "approved"
    assert approval["processing_status"] == "needs_review"
    assert "ARMORIQ_ENFORCEMENT must be required" in approval["processing_message"]

    replay = client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        json={"details_hash": details_hash, "note": "Double-click replay."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert replay.status_code == 200
    assert replay.json()["processing_status"] == "needs_review"

    retry = client.post(
        f"/api/v1/approvals/{approval_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert retry.status_code == 200
    assert retry.json()["processing_status"] == "needs_review"

    approval_row = db.query(PaymentApproval).filter(PaymentApproval.id == approval_id).one()
    attempt_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    failed_attempt = PaymentAttempt(
        id=attempt_id,
        household_id=seed_data["h1"].id,
        bill_id=approval_row.bill_id,
        approval_id=approval_row.id,
        idempotency_key=f"approval-{approval_id}",
        client_reference=f"ATTEMPT-{attempt_id}",
        amount=approval_row.amount,
        currency=approval_row.currency,
        destination_account_number=approval_row.destination_account_number,
        destination_account_number_masked=approval_row.destination_account_number_masked,
        destination_ifsc=approval_row.destination_ifsc,
        initiated_by_type="user",
        initiated_by_user_id=seed_data["owner_id"],
        decision="allow",
        status="failed",
        reason_code="bank_error",
        message="Witness reconciliation confirmed no bank transaction.",
        created_at=now - timedelta(minutes=1),
        completed_at=now,
    )
    db.add(failed_attempt)
    db.flush()
    db.add(
        WitnessReportModel(
            id=report_id,
            household_id=seed_data["h1"].id,
            attempt_id=attempt_id,
            bill_id=approval_row.bill_id,
            expected_outcome="payment_absent",
            verdict="confirmed_no_payment",
            ledger_match_count=0,
            matched_transactions=[],
            summary="Witness confirms no payment found.",
            ledger_source="mock_bank_sqlite",
            read_only=True,
            window_start=now - timedelta(hours=1),
            window_end=now + timedelta(hours=1),
            checked_at=now,
        )
    )
    db.flush()
    failed_attempt.latest_witness_report_id = report_id
    db.commit()

    for name, value in {
        "LLM_PROVIDER": "gemini",
        "ARMORIQ_ENFORCEMENT": "required",
        "ARMORIQ_ROUTE": "proxy",
        "ARMORIQ_API_KEY": "test-key",
        "KEEPER_MCP_PUBLIC_URL": "https://mcp.example.test/mcp",
        "KEEPER_MCP_INBOUND_SECRET": "test-inbound",
        "ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN": "test-inbound",
        "MOCK_BANK_AUTH_TOKEN": "test-bank",
        "SUPABASE_JWT_SECRET": "keeper-test-only-secret-key-with-more-than-32-bytes",
        "GEMINI_API_KEY": "test-gemini-key",
    }.items():
        monkeypatch.setattr(settings, name, value)

    scheduled = []
    monkeypatch.setattr(
        "backend.app.api.v1.approvals.run_approved_payment",
        lambda *args: scheduled.append(args),
    )
    retry_after_witness = client.post(
        f"/api/v1/approvals/{approval_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert retry_after_witness.status_code == 200
    assert retry_after_witness.json()["processing_status"] == "processing"
    assert scheduled == [(approval_id, "owner@test.com", f"approval-{approval_id}-retry-1")]

    payments = client.get("/api/v1/payments", headers={"Authorization": f"Bearer {token}"}).json()["items"]
    assert all(attempt["status"] != "succeeded" for attempt in payments)

def test_payment_request_fails_closed_without_approved_proxy(client, seed_data):
    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    bill_payload = {
        "title": "Normal Electricity",
        "category": "electricity",
        "amount": "1200.00",
        "currency": "INR",
        "due_date": "2026-10-30",
        "destination_account_number": "112233440101",
        "destination_ifsc": "HDFC0001234",
    }
    create_res = client.post("/api/v1/bills", json=bill_payload, headers={"Authorization": f"Bearer {token}"})
    bill_id = create_res.json()["id"]

    idemp_key = "stable-key-12345"
    # Without the real ArmorIQ proxy there is no payment attempt or bank request.
    res1 = client.post(f"/api/v1/bills/{bill_id}/pay", json={"idempotency_key": idemp_key}, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 503
    assert "No payment was sent" in res1.json()["error"]["message"]
    bill_state = client.get(f"/api/v1/bills/{bill_id}", headers={"Authorization": f"Bearer {token}"}).json()["bill"]
    assert bill_state["status"] == "needs_review"

    res2 = client.post(f"/api/v1/bills/{bill_id}/pay", json={"idempotency_key": idemp_key}, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 503
    other_key = client.post(
        f"/api/v1/bills/{bill_id}/pay",
        json={"idempotency_key": "different-key"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert other_key.status_code == 409
    assert other_key.json()["error"]["code"] == "idempotency_conflict"
    attempts = client.get("/api/v1/payments", headers={"Authorization": f"Bearer {token}"}).json()["items"]
    assert attempts == []

def test_idempotency_key_cannot_be_reused_for_another_bill(client, seed_data):
    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    shared_key = "one-key-one-bill"
    bill_payload = {
        "title": "Unapproved first bill",
        "category": "electricity",
        "amount": "1200.00",
        "currency": "INR",
        "due_date": "2026-11-10",
        "destination_account_number": "999900001234",
        "destination_ifsc": "FAKE0000666",
    }
    first_bill = client.post("/api/v1/bills", json=bill_payload, headers=headers).json()
    first_pay = client.post(
        f"/api/v1/bills/{first_bill['id']}/pay",
        json={"idempotency_key": shared_key},
        headers=headers,
    )
    assert first_pay.status_code == 200
    assert first_pay.json()["attempt"]["status"] == "blocked"

    second_bill_payload = {
        **bill_payload,
        "title": "Different bill",
        "destination_account_number": "112233440101",
        "destination_ifsc": "HDFC0001234",
    }
    second_bill = client.post("/api/v1/bills", json=second_bill_payload, headers=headers).json()
    second_pay = client.post(
        f"/api/v1/bills/{second_bill['id']}/pay",
        json={"idempotency_key": shared_key},
        headers=headers,
    )
    assert second_pay.status_code == 409
    assert second_pay.json()["error"]["code"] == "idempotency_conflict"

def test_policy_version_conflict(client, seed_data):
    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    # Current version is 1. Try to update with wrong version
    update_res = client.put(
        "/api/v1/policy",
        json={"auto_pay_limit": "15000.00", "approval_ttl_minutes": 720, "expected_version": 99},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_res.status_code == 409
    assert update_res.json()["error"]["code"] == "version_conflict"

    # Update with correct version
    ok_res = client.put(
        "/api/v1/policy",
        json={"auto_pay_limit": "15000.00", "approval_ttl_minutes": 720, "expected_version": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert ok_res.status_code == 200
    assert ok_res.json()["auto_pay_limit"] == "15000.00"
    assert ok_res.json()["version"] == 2

def test_legacy_demo_payment_endpoint_is_not_registered(client):
    response = client.post("/api/v1/demo/scenarios/normal_payment/run")
    assert response.status_code == 404


def test_approval_schedules_agent_processing_when_services_are_configured(
    client, seed_data, monkeypatch
):
    token = make_auth_token(seed_data["owner_id"], "owner@test.com")
    headers = {"Authorization": f"Bearer {token}"}
    for name, value in {
        "LLM_PROVIDER": "gemini",
        "ARMORIQ_ENFORCEMENT": "required",
        "ARMORIQ_ROUTE": "proxy",
        "ARMORIQ_API_KEY": "test-key",
        "KEEPER_MCP_PUBLIC_URL": "https://mcp.example.test/mcp",
        "KEEPER_MCP_INBOUND_SECRET": "test-inbound",
        "ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN": "test-inbound",
        "MOCK_BANK_AUTH_TOKEN": "test-bank",
        "SUPABASE_JWT_SECRET": "keeper-test-only-secret-key-with-more-than-32-bytes",
        "GEMINI_API_KEY": "test-gemini-key",
    }.items():
        monkeypatch.setattr(settings, name, value)

    bill = client.post(
        "/api/v1/bills",
        headers=headers,
        json={
            "title": "Approved insurance bill",
            "category": "insurance",
            "amount": "48000.00",
            "currency": "INR",
            "due_date": "2026-11-30",
            "destination_account_number": "112233440101",
            "destination_ifsc": "HDFC0001234",
        },
    )
    assert bill.status_code == 201
    outcome = client.post(
        f"/api/v1/bills/{bill.json()['id']}/pay",
        headers=headers,
        json={"idempotency_key": "approval-flow-key"},
    )
    assert outcome.status_code == 200
    approval = outcome.json()["approval"]

    scheduled = []
    monkeypatch.setattr(
        "backend.app.api.v1.approvals.run_approved_payment",
        lambda *args: scheduled.append(args),
    )
    approved = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=headers,
        json={"details_hash": approval["details_hash"]},
    )

    assert approved.status_code == 200
    assert approved.json()["processing_status"] == "processing"
    assert scheduled == [(approval["id"], "owner@test.com")]
