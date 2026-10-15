import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.app.models.models import PaymentApproval, WitnessReportModel, PaymentAttempt, SecurityEvent
from backend.witness.verifier import WitnessVerifier

class WitnessService:
    def __init__(self, verifier: Optional[WitnessVerifier] = None):
        self.verifier = verifier or WitnessVerifier()

    def verify_and_record(
        self,
        db: Session,
        attempt: PaymentAttempt,
        expected_destination_account: str,
    ) -> WitnessReportModel:
        reconciling = attempt.status == "executing"
        expected_outcome = "payment_absent" if reconciling else (
            "payment_present" if attempt.status == "succeeded" else "payment_absent"
        )
        
        attempt_created_at = attempt.created_at
        if attempt_created_at and attempt_created_at.tzinfo is None:
            attempt_created_at = attempt_created_at.replace(tzinfo=timezone.utc)

        rep = self.verifier.verify_payment_attempt(
            client_reference=attempt.client_reference,
            expected_amount=str(attempt.amount),
            expected_currency=attempt.currency,
            expected_destination_account=expected_destination_account,
            expected_ifsc=attempt.destination_ifsc,
            expected_outcome=expected_outcome,
            attempt_created_at=attempt_created_at,
        )
        if reconciling and rep["verdict"] == "mismatch_detected" and rep["ledger_match_count"] > 0:
            present_result = self.verifier.verify_payment_attempt(
                client_reference=attempt.client_reference,
                expected_amount=str(attempt.amount),
                expected_currency=attempt.currency,
                expected_destination_account=expected_destination_account,
                expected_ifsc=attempt.destination_ifsc,
                expected_outcome="payment_present",
                attempt_created_at=attempt_created_at,
            )
            if present_result["verdict"] == "confirmed_paid":
                rep = present_result

        now = datetime.now(timezone.utc)
        report_id = str(uuid.uuid4())
        
        window_start = datetime.fromisoformat(rep["window_start"])
        window_end = datetime.fromisoformat(rep["window_end"])
        checked_at = datetime.fromisoformat(rep["checked_at"])

        report = WitnessReportModel(
            id=report_id,
            household_id=attempt.household_id,
            attempt_id=attempt.id,
            bill_id=attempt.bill_id,
            expected_outcome=rep["expected_outcome"],
            verdict=rep["verdict"],
            ledger_match_count=rep["ledger_match_count"],
            matched_transactions=rep["matched_transactions"],
            summary=rep["summary"],
            ledger_source="mock_bank_sqlite",
            read_only=True,
            window_start=window_start,
            window_end=window_end,
            checked_at=checked_at,
        )
        db.add(report)
        db.flush()
        attempt.latest_witness_report_id = report_id

        if reconciling and rep["verdict"] == "confirmed_paid" and rep["matched_transactions"]:
            attempt.status = "succeeded"
            attempt.bank_reference = rep["matched_transactions"][0]["bank_txn_id"]
            attempt.completed_at = checked_at
            attempt.message = "Payment confirmed by Witness reconciliation against the mock-bank ledger."
            attempt.bill.status = "paid"
            attempt.bill.paid_at = checked_at
            attempt.bill.processing_idempotency_key = None
            if attempt.approval_id:
                approval = db.query(PaymentApproval).filter(PaymentApproval.id == attempt.approval_id).first()
                if approval:
                    approval.status = "consumed"
                    approval.processing_status = "paid"
                    approval.processing_message = attempt.message
            db.add(
                SecurityEvent(
                    household_id=attempt.household_id,
                    bill_id=attempt.bill_id,
                    attempt_id=attempt.id,
                    event_type="payment_executed",
                    severity="info",
                    actor_type="system",
                    message=attempt.message,
                    details={"bank_reference": attempt.bank_reference, "reconciled_by_witness": True},
                    created_at=now,
                )
            )
        elif reconciling and rep["verdict"] == "confirmed_no_payment":
            attempt.status = "failed"
            attempt.reason_code = "bank_error"
            attempt.completed_at = checked_at
            attempt.message = "Witness reconciliation found no transaction in the mock-bank ledger. No payment was made."
            attempt.bill.status = "failed"
            attempt.bill.processing_idempotency_key = None
            if attempt.approval_id:
                approval = db.query(PaymentApproval).filter(PaymentApproval.id == attempt.approval_id).first()
                if approval:
                    approval.processing_status = "needs_review"
                    approval.processing_message = "Witness found no bank transaction. Review before retrying."
            db.add(
                SecurityEvent(
                    household_id=attempt.household_id,
                    bill_id=attempt.bill_id,
                    attempt_id=attempt.id,
                    event_type="payment_failed",
                    severity="warning",
                    actor_type="system",
                    message=attempt.message,
                    details={"reconciled_by_witness": True},
                    created_at=now,
                )
            )
        elif reconciling:
            attempt.bill.status = "needs_review"
            if attempt.approval_id:
                approval = db.query(PaymentApproval).filter(PaymentApproval.id == attempt.approval_id).first()
                if approval:
                    approval.processing_status = "needs_review"
                    approval.processing_message = "Witness could not confirm an exact ledger outcome. Do not retry yet."

        # Security event for Witness check
        sec_event_type = "witness_verified" if rep["verdict"] in ("confirmed_paid", "confirmed_no_payment") else "witness_mismatch"
        sec_severity = "info" if rep["verdict"] in ("confirmed_paid", "confirmed_no_payment") else "critical"
        sec_event = SecurityEvent(
            household_id=attempt.household_id,
            bill_id=attempt.bill_id,
            attempt_id=attempt.id,
            event_type=sec_event_type,
            severity=sec_severity,
            actor_type="witness",
            message=rep["summary"],
            details={
                "verdict": rep["verdict"],
                "ledger_match_count": rep["ledger_match_count"],
                "report_id": report_id,
            },
            created_at=now,
        )
        db.add(sec_event)
        db.commit()
        db.refresh(report)
        return report
