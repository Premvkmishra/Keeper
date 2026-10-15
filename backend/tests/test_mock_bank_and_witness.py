import uuid
from datetime import date
from backend.mock_bank.main import get_db_path
from backend.app.models.models import Bill, PaymentAttempt
from backend.app.services.witness_service import WitnessService
from backend.witness.verifier import WitnessVerifier

def test_mock_bank_health(mock_bank_client):
    res = mock_bank_client.get("/_internal/mock-bank/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_mock_bank_payment_and_idempotency(mock_bank_client):
    from backend.app.core.config import settings

    req_payload = {
        "client_reference": "REF-TEST-001",
        "amount": "2400.00",
        "currency": "INR",
        "destination_account_number": "112233440101",
        "destination_ifsc": "HDFC0001234",
    }
    headers = {"Authorization": f"Bearer {settings.MOCK_BANK_AUTH_TOKEN}"}
    unauthenticated = mock_bank_client.post("/_internal/mock-bank/bank/v1/payments", json=req_payload)
    assert unauthenticated.status_code == 401

    # 1. First execution
    res1 = mock_bank_client.post("/_internal/mock-bank/bank/v1/payments", json=req_payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["status"] == "posted"
    assert "TXN-" in data1["bank_txn_id"]

    # 2. Duplicate idempotent call returns same bank_txn_id
    res2 = mock_bank_client.post("/_internal/mock-bank/bank/v1/payments", json=req_payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["bank_txn_id"] == data1["bank_txn_id"]

    # 3. Conflicting request with same client_reference but different amount
    conflict_payload = dict(req_payload)
    conflict_payload["amount"] = "5000.00"
    res3 = mock_bank_client.post("/_internal/mock-bank/bank/v1/payments", json=conflict_payload, headers=headers)
    assert res3.status_code == 409

def test_witness_verification(mock_bank_client):
    from backend.app.core.config import settings

    client_ref = "REF-TEST-002"
    req_payload = {
        "client_reference": client_ref,
        "amount": "2400.00",
        "currency": "INR",
        "destination_account_number": "112233440101",
        "destination_ifsc": "HDFC0001234",
    }
    # Before payment: verify absence
    verifier = WitnessVerifier(str(get_db_path()))
    rep_before = verifier.verify_payment_attempt(
        client_reference=client_ref,
        expected_amount="2400.00",
        expected_currency="INR",
        expected_destination_account="112233440101",
        expected_ifsc="HDFC0001234",
        expected_outcome="payment_absent",
    )
    assert rep_before["verdict"] == "confirmed_no_payment"
    assert rep_before["ledger_match_count"] == 0

    # Post payment
    mock_bank_client.post(
        "/_internal/mock-bank/bank/v1/payments",
        json=req_payload,
        headers={"Authorization": f"Bearer {settings.MOCK_BANK_AUTH_TOKEN}"},
    )

    # After payment: verify presence
    rep_after = verifier.verify_payment_attempt(
        client_reference=client_ref,
        expected_amount="2400.00",
        expected_currency="INR",
        expected_destination_account="112233440101",
        expected_ifsc="HDFC0001234",
        expected_outcome="payment_present",
    )
    assert rep_after["verdict"] == "confirmed_paid"
    assert rep_after["ledger_match_count"] == 1

    # Mismatch detection: wrong expected amount
    rep_mismatch = verifier.verify_payment_attempt(
        client_reference=client_ref,
        expected_amount="9999.00",
        expected_currency="INR",
        expected_destination_account="112233440101",
        expected_ifsc="HDFC0001234",
        expected_outcome="payment_present",
    )
    assert rep_mismatch["verdict"] == "mismatch_detected"

def test_witness_reconciles_executing_attempts(mock_bank_client, db, seed_data):
    from backend.app.core.config import settings

    def make_attempt(reference):
        bill = Bill(
            household_id=seed_data["h1"].id,
            title=f"Bill for {reference}",
            category="electricity",
            amount=2400.00,
            currency="INR",
            due_date=date(2026, 11, 10),
            status="processing",
            source="manual",
            destination_account_number="112233440101",
            destination_account_number_masked="••••••••0101",
            destination_ifsc="HDFC0001234",
            destination_matches_approved=True,
        )
        db.add(bill)
        db.flush()
        attempt = PaymentAttempt(
            household_id=seed_data["h1"].id,
            bill_id=bill.id,
            idempotency_key=f"key-{reference}",
            client_reference=reference,
            amount=2400.00,
            currency="INR",
            destination_account_number="112233440101",
            destination_account_number_masked="••••••••0101",
            destination_ifsc="HDFC0001234",
            initiated_by_type="user",
            decision="allow",
            status="executing",
            reason_code="bank_error",
            message="Bank response was ambiguous.",
        )
        db.add(attempt)
        db.commit()
        return bill, attempt

    token = settings.MOCK_BANK_AUTH_TOKEN
    headers = {"Authorization": f"Bearer {token}"}
    paid_bill, posted_attempt = make_attempt("REF-RECONCILE-POSTED")
    bank_response = mock_bank_client.post(
        "/_internal/mock-bank/bank/v1/payments",
        json={
            "client_reference": posted_attempt.client_reference,
            "amount": "2400.00",
            "currency": "INR",
            "destination_account_number": "112233440101",
            "destination_ifsc": "HDFC0001234",
        },
        headers=headers,
    )
    assert bank_response.status_code == 201
    paid_report = WitnessService().verify_and_record(
        db, posted_attempt, expected_destination_account=posted_attempt.destination_account_number
    )
    assert paid_report.verdict == "confirmed_paid"
    assert posted_attempt.status == "succeeded"
    assert posted_attempt.bank_reference == bank_response.json()["bank_txn_id"]
    assert paid_bill.status == "paid"

    unpaid_bill, absent_attempt = make_attempt("REF-RECONCILE-ABSENT")
    absent_report = WitnessService().verify_and_record(
        db, absent_attempt, expected_destination_account=absent_attempt.destination_account_number
    )
    assert absent_report.verdict == "confirmed_no_payment"
    assert absent_attempt.status == "failed"
    assert unpaid_bill.status == "failed"
