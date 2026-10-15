import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from sqlalchemy import text
from backend.app.core.config import settings
from backend.app.models.models import (
    Bill as BillModel,
    PaymentAttempt as PaymentAttemptModel,
    PaymentApproval as PaymentApprovalModel,
    SecurityEvent,
    WitnessReportModel,
)
from backend.app.services.policy_engine import PolicyEngine, PolicyCheckResult
from backend.app.services.witness_service import WitnessService
from backend.app.schemas.schemas import (
    PaymentOutcome,
    PaymentAttempt as PaymentAttemptSchema,
    Bill as BillSchema,
    Approval as ApprovalSchema,
    WitnessReport as WitnessReportSchema,
    MatchedTransaction,
    InitiatorType,
)

logger = logging.getLogger(__name__)

def bill_to_schema(b: BillModel) -> BillSchema:
    return BillSchema(
        id=str(b.id),
        biller_id=str(b.biller_id) if b.biller_id else None,
        biller_name=b.biller.name if b.biller else None,
        title=b.title,
        category=b.category,
        amount=f"{float(b.amount):.2f}",
        currency=b.currency,
        due_date=str(b.due_date),
        status=b.status,
        source=b.source,
        invoice_ref=b.invoice_ref,
        destination_account_number_masked=b.destination_account_number_masked,
        destination_ifsc=b.destination_ifsc,
        destination_matches_approved=b.destination_matches_approved,
        created_at=b.created_at.isoformat(),
        updated_at=b.updated_at.isoformat(),
        paid_at=b.paid_at.isoformat() if b.paid_at else None,
    )

def attempt_to_schema(at: PaymentAttemptModel, bill_title: str) -> PaymentAttemptSchema:
    return PaymentAttemptSchema(
        id=str(at.id),
        bill_id=str(at.bill_id),
        bill_title=bill_title,
        approval_id=str(at.approval_id) if at.approval_id else None,
        amount=f"{float(at.amount):.2f}",
        currency=at.currency,
        destination_account_number_masked=at.destination_account_number_masked,
        destination_ifsc=at.destination_ifsc,
        initiated_by_type=at.initiated_by_type,
        decision=at.decision,
        status=at.status,
        reason_code=at.reason_code,
        message=at.message,
        bank_reference=at.bank_reference,
        created_at=at.created_at.isoformat() if at.created_at else "",
        completed_at=at.completed_at.isoformat() if at.completed_at else None,
        latest_witness_report_id=str(at.latest_witness_report_id) if at.latest_witness_report_id else None,
    )

def approval_to_schema(a: PaymentApprovalModel) -> ApprovalSchema:
    return ApprovalSchema(
        id=str(a.id),
        bill_id=str(a.bill_id),
        bill_title=a.bill.title if a.bill else "Bill",
        biller_name=a.bill.biller.name if a.bill and a.bill.biller else None,
        amount=f"{float(a.amount):.2f}",
        currency=a.currency,
        destination_account_number_masked=a.destination_account_number_masked,
        destination_ifsc=a.destination_ifsc,
        details_hash=a.details_hash,
        status=a.status,
        processing_status=a.processing_status,
        processing_message=a.processing_message,
        reason_code=a.reason_code,
        requested_by_type=a.requested_by_type,
        requested_at=a.requested_at.isoformat(),
        expires_at=a.expires_at.isoformat(),
        decided_at=a.decided_at.isoformat() if a.decided_at else None,
        decided_by_name=a.decided_by_name,
        decision_note=a.decision_note,
        invalidated_reason=a.invalidated_reason,
    )

def witness_to_schema(w: WitnessReportModel) -> WitnessReportSchema:
    txns = []
    if w.matched_transactions:
        for t in w.matched_transactions:
            txns.append(
                MatchedTransaction(
                    bank_txn_id=t.get("bank_txn_id", ""),
                    amount=f"{float(t.get('amount', 0)):.2f}",
                    currency=t.get("currency", "INR"),
                    destination_account_number_masked=t.get("destination_account_number_masked", ""),
                    destination_ifsc=t.get("destination_ifsc", ""),
                    bank_status=t.get("bank_status", "posted"),
                    created_at=t.get("created_at", ""),
                )
            )

    return WitnessReportSchema(
        id=str(w.id),
        attempt_id=str(w.attempt_id),
        bill_id=str(w.bill_id),
        expected_outcome=w.expected_outcome,
        verdict=w.verdict,
        ledger_match_count=w.ledger_match_count,
        matched_transactions=txns,
        summary=w.summary,
        ledger_source=w.ledger_source,
        read_only=True,
        window_start=w.window_start.isoformat(),
        window_end=w.window_end.isoformat(),
        checked_at=w.checked_at.isoformat(),
    )

class PaymentExecutionService:
    def __init__(self, witness_service: Optional[WitnessService] = None):
        self.witness_service = witness_service or WitnessService()

    def _lookup_bank(self, client_reference: str) -> Tuple[Optional[str], Optional[str]]:
        """Read-only lookup by client_reference. Returns (txn_id, error)."""
        lookup_url = f"{settings.mock_bank_base_url}/bank/v1/payments/{client_reference}"
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(
                    lookup_url,
                    headers={"Authorization": f"Bearer {settings.MOCK_BANK_AUTH_TOKEN or ''}"},
                )
                if res.status_code == 200:
                    return res.json().get("bank_txn_id"), None
                if res.status_code == 404:
                    return None, "not_found"
                return None, f"lookup_http_{res.status_code}"
        except Exception as e:
            return None, f"lookup_failed:{type(e).__name__}"

    def _call_mock_bank(self, payload: dict) -> Tuple[str, Optional[str], Optional[str]]:
        """Invokes the mock bank. Returns (outcome, txn_id, error) where outcome is
        'posted' | 'rejected' | 'ambiguous'."""
        bank_url = f"{settings.mock_bank_base_url}/bank/v1/payments"
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.post(
                    bank_url,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.MOCK_BANK_AUTH_TOKEN or ''}"},
                )
                if res.status_code in (200, 201):
                    return "posted", res.json().get("bank_txn_id"), None
                return "rejected", None, f"Bank error HTTP {res.status_code}: {res.text}"
        except Exception as e:
            txn_id, lookup_err = self._lookup_bank(payload["client_reference"])
            if txn_id:
                return "posted", txn_id, None
            if lookup_err == "not_found":
                return "rejected", None, f"Bank connection failure: {str(e)}"
            return "ambiguous", None, f"Bank response lost; reconcile by client reference. ({e})"

    def execute_payment(
        self,
        db: Session,
        bill: BillModel,
        household_id: str,
        idempotency_key: str,
        initiated_by_type: InitiatorType = "user",
        initiated_by_user_id: Optional[str] = None,
        approval_id: Optional[str] = None,
        policy_result: Optional[PolicyCheckResult] = None,
    ) -> Tuple[PaymentAttemptModel, PaymentOutcome]:
        now = datetime.now(timezone.utc)

        try:
            db.execute(text("SELECT 1"))
        except Exception as db_err:
            raise RuntimeError(
                "Application database is unavailable; refusing to send a new payment."
            ) from db_err

        from backend.mock_bank.main import init_bank_db
        init_bank_db()

        # 1. Idempotency Check: look up existing attempt with this idempotency_key for this household
        existing_attempt = (
            db.query(PaymentAttemptModel)
            .filter(
                PaymentAttemptModel.household_id == household_id,
                PaymentAttemptModel.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing_attempt:
            if str(existing_attempt.bill_id) != str(bill.id):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "idempotency_conflict",
                        "message": "This idempotency key already belongs to a different bill.",
                    },
                )
            logger.info(f"Idempotent replay detected for key {idempotency_key}")
            appr = (
                db.query(PaymentApprovalModel).filter(PaymentApprovalModel.id == existing_attempt.approval_id).first()
                if existing_attempt.approval_id
                else None
            )
            wit_rep = (
                db.query(WitnessReportModel)
                .filter(WitnessReportModel.id == existing_attempt.latest_witness_report_id)
                .first()
                if existing_attempt.latest_witness_report_id
                else None
            )
            outcome = PaymentOutcome(
                decision=existing_attempt.decision,
                reason_code=existing_attempt.reason_code,
                message=existing_attempt.message,
                idempotent_replay=True,
                attempt=attempt_to_schema(existing_attempt, bill.title),
                bill=bill_to_schema(bill),
                approval=approval_to_schema(appr) if appr else None,
                witness_report=witness_to_schema(wit_rep) if wit_rep else None,
            )
            return existing_attempt, outcome

        # 2. Run Keeper's authoritative policy checks
        check_result = policy_result or PolicyEngine.evaluate(
            db=db,
            bill=bill,
            household_id=household_id,
            initiated_by_type=initiated_by_type,
            approval_id=approval_id,
            idempotency_key=idempotency_key,
        )

        attempt_id = str(uuid.uuid4())
        client_ref = f"ATTEMPT-{attempt_id}"

        # 3. Handle Decision: DENY
        if check_result.decision == "deny":
            attempt = PaymentAttemptModel(
                id=attempt_id,
                household_id=household_id,
                bill_id=bill.id,
                approval_id=check_result.approval.id if check_result.approval else None,
                idempotency_key=idempotency_key,
                client_reference=client_ref,
                amount=bill.amount,
                currency=bill.currency,
                destination_account_number=bill.destination_account_number,
                destination_account_number_masked=bill.destination_account_number_masked,
                destination_ifsc=bill.destination_ifsc,
                initiated_by_type=initiated_by_type,
                initiated_by_user_id=initiated_by_user_id,
                decision="deny",
                status="blocked",
                reason_code=check_result.reason_code,
                message=check_result.message,
                bank_reference=None,
                created_at=now,
                completed_at=now,
            )
            db.add(attempt)
            db.commit()

            sec_event = SecurityEvent(
                household_id=household_id,
                bill_id=bill.id,
                attempt_id=attempt.id,
                event_type=check_result.security_event_type or "policy_denied",
                severity=check_result.security_event_severity,
                actor_type="agent" if initiated_by_type == "agent" else "user",
                message=check_result.message,
                details={
                    "reason_code": check_result.reason_code,
                    "destination_account_masked": bill.destination_account_number_masked,
                    "destination_ifsc": bill.destination_ifsc,
                    "decided_by": "keeper_policy",
                    "next_action": (
                        "Verify the destination through a trusted channel. Ordinary approval cannot override this."
                        if check_result.reason_code == "beneficiary_not_approved"
                        else "Review the policy reason and resolve the underlying issue."
                    ),
                },
                created_at=now,
            )
            db.add(sec_event)
            db.commit()

            wit_rep = self.witness_service.verify_and_record(
                db=db,
                attempt=attempt,
                expected_destination_account=bill.destination_account_number,
            )

            outcome = PaymentOutcome(
                decision="deny",
                reason_code=check_result.reason_code,
                message=check_result.message,
                idempotent_replay=False,
                attempt=attempt_to_schema(attempt, bill.title),
                bill=bill_to_schema(bill),
                approval=approval_to_schema(check_result.approval) if check_result.approval else None,
                witness_report=witness_to_schema(wit_rep),
            )
            return attempt, outcome

        # 4. Handle Decision: REQUIRE_APPROVAL
        if check_result.decision == "require_approval":
            attempt = PaymentAttemptModel(
                id=attempt_id,
                household_id=household_id,
                bill_id=bill.id,
                approval_id=check_result.approval.id if check_result.approval else None,
                idempotency_key=idempotency_key,
                client_reference=client_ref,
                amount=bill.amount,
                currency=bill.currency,
                destination_account_number=bill.destination_account_number,
                destination_account_number_masked=bill.destination_account_number_masked,
                destination_ifsc=bill.destination_ifsc,
                initiated_by_type=initiated_by_type,
                initiated_by_user_id=initiated_by_user_id,
                decision="require_approval",
                status="requires_approval",
                reason_code=check_result.reason_code,
                message=check_result.message,
                bank_reference=None,
                created_at=now,
                completed_at=None,
            )
            db.add(attempt)
            db.commit()

            sec_event = SecurityEvent(
                household_id=household_id,
                bill_id=bill.id,
                attempt_id=attempt.id,
                event_type="approval_requested",
                severity="info",
                actor_type="agent" if initiated_by_type == "agent" else "user",
                message=f"High-value payment of {bill.amount} {bill.currency} requires human approval.",
                details={
                    "approval_id": check_result.approval.id if check_result.approval else None,
                    "amount": str(bill.amount),
                },
                created_at=now,
            )
            db.add(sec_event)
            db.commit()

            outcome = PaymentOutcome(
                decision="require_approval",
                reason_code=check_result.reason_code,
                message=check_result.message,
                idempotent_replay=False,
                attempt=attempt_to_schema(attempt, bill.title),
                bill=bill_to_schema(bill),
                approval=approval_to_schema(check_result.approval) if check_result.approval else None,
                witness_report=None,
            )
            return attempt, outcome

        # 5. Handle Decision: ALLOW -> Execute Simulated Transfer
        attempt = PaymentAttemptModel(
            id=attempt_id,
            household_id=household_id,
            bill_id=bill.id,
            approval_id=check_result.approval.id if check_result.approval else None,
            idempotency_key=idempotency_key,
            client_reference=client_ref,
            amount=bill.amount,
            currency=bill.currency,
            destination_account_number=bill.destination_account_number,
            destination_account_number_masked=bill.destination_account_number_masked,
            destination_ifsc=bill.destination_ifsc,
            initiated_by_type=initiated_by_type,
            initiated_by_user_id=initiated_by_user_id,
            decision="allow",
            status="executing",
            reason_code=check_result.reason_code,
            message="Processing payment transfer with bank...",
            bank_reference=None,
            created_at=now,
            completed_at=None,
        )
        bill.status = "processing"
        bill.processing_idempotency_key = idempotency_key
        db.add(attempt)
        db.commit()

        bank_payload = {
            "client_reference": client_ref,
            "amount": f"{float(bill.amount):.2f}",
            "currency": bill.currency,
            "destination_account_number": bill.destination_account_number,
            "destination_ifsc": bill.destination_ifsc,
        }

        bank_outcome, bank_txn_id, error_msg = self._call_mock_bank(bank_payload)
        completed_time = datetime.now(timezone.utc)

        if bank_outcome == "ambiguous":
            attempt.status = "executing"
            attempt.reason_code = "bank_error"
            attempt.message = (
                "The payment outcome could not yet be verified. Keeper is checking the existing "
                "attempt against the mock-bank ledger. Do not submit another payment until reconciliation finishes."
            )
            db.commit()
            wit_rep = self.witness_service.verify_and_record(
                db=db,
                attempt=attempt,
                expected_destination_account=bill.destination_account_number,
            )
            if wit_rep.verdict == "confirmed_paid" and wit_rep.matched_transactions:
                first = wit_rep.matched_transactions[0]
                attempt.status = "succeeded"
                attempt.bank_reference = first.get("bank_txn_id")
                attempt.completed_at = completed_time
                attempt.message = "Payment executed successfully (reconciled after ambiguous bank response)."
                bill.status = "paid"
                bill.paid_at = completed_time
                if check_result.approval:
                    check_result.approval.status = "consumed"
                db.commit()
            outcome = PaymentOutcome(
                decision="allow",
                reason_code=attempt.reason_code,
                message=attempt.message,
                idempotent_replay=False,
                attempt=attempt_to_schema(attempt, bill.title),
                bill=bill_to_schema(bill),
                approval=approval_to_schema(check_result.approval) if check_result.approval else None,
                witness_report=witness_to_schema(wit_rep),
            )
            return attempt, outcome

        if bank_outcome == "posted" and bank_txn_id:
            attempt.status = "succeeded"
            attempt.bank_reference = bank_txn_id
            attempt.message = "Payment executed successfully."
            attempt.completed_at = completed_time

            bill.status = "paid"
            bill.paid_at = completed_time
            bill.processing_idempotency_key = None
            bill.processing_idempotency_key = None

            if check_result.approval:
                check_result.approval.status = "consumed"

            db.commit()

            sec_event = SecurityEvent(
                household_id=household_id,
                bill_id=bill.id,
                attempt_id=attempt.id,
                event_type="payment_executed",
                severity="info",
                actor_type="system",
                message=f"Simulated payment posted with bank txn {bank_txn_id}.",
                details={"bank_reference": bank_txn_id, "amount": str(bill.amount)},
                created_at=completed_time,
            )
            db.add(sec_event)
            db.commit()

            wit_rep = self.witness_service.verify_and_record(
                db=db,
                attempt=attempt,
                expected_destination_account=bill.destination_account_number,
            )

            outcome = PaymentOutcome(
                decision="allow",
                reason_code=check_result.reason_code,
                message="Payment processed and verified.",
                idempotent_replay=False,
                attempt=attempt_to_schema(attempt, bill.title),
                bill=bill_to_schema(bill),
                approval=approval_to_schema(check_result.approval) if check_result.approval else None,
                witness_report=witness_to_schema(wit_rep),
            )
            return attempt, outcome
        else:
            attempt.status = "failed"
            attempt.reason_code = "bank_error"
            attempt.message = error_msg or "Simulated bank payment failed."
            attempt.completed_at = completed_time
            bill.status = "failed"
            bill.processing_idempotency_key = None
            db.commit()

            sec_event = SecurityEvent(
                household_id=household_id,
                bill_id=bill.id,
                attempt_id=attempt.id,
                event_type="payment_failed",
                severity="critical",
                actor_type="system",
                message=f"Payment execution failed: {error_msg}",
                details={"error": error_msg},
                created_at=completed_time,
            )
            db.add(sec_event)
            db.commit()

            wit_rep = self.witness_service.verify_and_record(
                db=db,
                attempt=attempt,
                expected_destination_account=bill.destination_account_number,
            )

            outcome = PaymentOutcome(
                decision="allow",
                reason_code="bank_error",
                message=error_msg or "Bank transfer failed.",
                idempotent_replay=False,
                attempt=attempt_to_schema(attempt, bill.title),
                bill=bill_to_schema(bill),
                approval=approval_to_schema(check_result.approval) if check_result.approval else None,
                witness_report=witness_to_schema(wit_rep),
            )
            return attempt, outcome
