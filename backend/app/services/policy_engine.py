import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.models import (
    Bill,
    HouseholdPolicy,
    TrustedBiller,
    ApprovedBeneficiary,
    PaymentApproval,
    SecurityEvent,
)
from backend.app.schemas.schemas import Decision, ReasonCode, InitiatorType
from backend.app.services.risk_signals import detect_risk_signals

def compute_details_hash(bill_id: str, amount: str, currency: str, account: str, ifsc: str) -> str:
    norm_amount = f"{float(amount):.2f}"
    raw = f"{bill_id}:{norm_amount}:{currency}:{account}:{ifsc}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

class PolicyCheckResult:
    def __init__(
        self,
        decision: Decision,
        reason_code: ReasonCode,
        message: str,
        approval: Optional[PaymentApproval] = None,
        security_event_type: Optional[str] = None,
        security_event_severity: str = "info",
    ):
        self.decision = decision
        self.reason_code = reason_code
        self.message = message
        self.approval = approval
        self.security_event_type = security_event_type
        self.security_event_severity = security_event_severity

class PolicyEngine:
    @staticmethod
    def evaluate(
        db: Session,
        bill: Bill,
        household_id: str,
        initiated_by_type: InitiatorType = "user",
        approval_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        allow_review_retry: bool = False,
    ) -> PolicyCheckResult:
        now = datetime.now(timezone.utc)
        
        # 1. Bill status check
        if bill.status == "paid":
            return PolicyCheckResult(
                decision="deny",
                reason_code="already_paid",
                message="This bill has already been paid.",
                security_event_type="policy_denied",
                security_event_severity="warning",
            )
        if bill.status == "processing" and not (
            idempotency_key and bill.processing_idempotency_key == idempotency_key
        ):
            return PolicyCheckResult(
                decision="deny",
                reason_code="bill_not_payable",
                message="This bill already has a payment request in progress. Reconcile it before retrying.",
                security_event_type="duplicate_blocked",
                security_event_severity="warning",
            )
        if bill.status == "needs_review" and not (
            allow_review_retry
            and idempotency_key
            and bill.processing_idempotency_key == idempotency_key
        ):
            return PolicyCheckResult(
                decision="deny",
                reason_code="bill_not_payable",
                message="This bill needs review before it can be paid again.",
                security_event_type="policy_denied",
                security_event_severity="warning",
            )
        if bill.status in ("cancelled", "blocked"):
            return PolicyCheckResult(
                decision="deny",
                reason_code="bill_not_payable",
                message=f"This bill cannot be paid right now (status: {bill.status}).",
                security_event_type="policy_denied",
                security_event_severity="warning",
            )

        # 2. Currency check
        if bill.currency != "INR":
            return PolicyCheckResult(
                decision="deny",
                reason_code="currency_mismatch",
                message=f"Unsupported currency: {bill.currency}.",
                security_event_type="policy_denied",
                security_event_severity="warning",
            )

        # 3. Trusted biller check
        if bill.biller_id:
            biller = (
                db.query(TrustedBiller)
                .filter(TrustedBiller.id == bill.biller_id, TrustedBiller.household_id == household_id)
                .first()
            )
            if not biller:
                return PolicyCheckResult(
                    decision="deny",
                    reason_code="biller_not_trusted",
                    message="Biller is not on your trusted list.",
                    security_event_type="biller_untrusted",
                    security_event_severity="critical",
                )
            if biller.status == "suspended":
                return PolicyCheckResult(
                    decision="deny",
                    reason_code="biller_suspended",
                    message="Biller is paused. Payments are currently blocked.",
                    security_event_type="policy_denied",
                    security_event_severity="warning",
                )

        # 4. Approved Beneficiary check (Authoritative Keeper security invariant)
        ben_query = (
            db.query(ApprovedBeneficiary)
            .filter(
                ApprovedBeneficiary.household_id == household_id,
                ApprovedBeneficiary.account_number == bill.destination_account_number,
                ApprovedBeneficiary.ifsc == bill.destination_ifsc,
                ApprovedBeneficiary.status == "active",
            )
        )
        if bill.biller_id:
            ben_query = ben_query.filter(ApprovedBeneficiary.biller_id == bill.biller_id)

        matching_ben = ben_query.first()
        risk_hits = detect_risk_signals(bill.title or "", bill.invoice_ref or "")
        if not matching_ben:
            bill.destination_matches_approved = False
            bill.status = "blocked"
            db.commit()
            extra = ""
            if risk_hits:
                extra = " The bill also contains urgent or coercive language. Urgency does not make an unapproved destination safe."
            return PolicyCheckResult(
                decision="deny",
                reason_code="beneficiary_not_approved",
                message=(
                    "Payment blocked because this bill directs money to an account that is not an "
                    "approved beneficiary. Human approval cannot override this restriction. Verify "
                    "the destination through a trusted channel before proceeding."
                    + extra
                ),
                security_event_type="beneficiary_mismatch",
                security_event_severity="critical",
            )

        bill.destination_matches_approved = True

        # 5. Payment limits and exact-detail approval evaluation
        policy = (
            db.query(HouseholdPolicy)
            .filter(HouseholdPolicy.household_id == household_id)
            .first()
        )
        limit = float(policy.auto_pay_limit) if policy else 10000.00
        ttl_minutes = policy.approval_ttl_minutes if policy else 1440
        bill_amount = float(bill.amount)
        hard_limit = float(settings.HARD_PAYMENT_LIMIT)
        if bill_amount > hard_limit:
            bill.status = "blocked"
            db.commit()
            return PolicyCheckResult(
                decision="deny",
                reason_code="amount_exceeds_limit",
                message=(
                    f"Payment blocked because ₹{bill_amount:.2f} exceeds the hard security limit "
                    f"of ₹{hard_limit:.2f}. Ordinary approval cannot override this restriction."
                ),
                security_event_type="policy_denied",
                security_event_severity="critical",
            )

        current_hash = compute_details_hash(
            str(bill.id),
            f"{bill_amount:.2f}",
            bill.currency,
            bill.destination_account_number,
            bill.destination_ifsc,
        )

        # Case A: Within limit
        if bill_amount <= limit:
            return PolicyCheckResult(
                decision="allow",
                reason_code="within_limit",
                message="Within your automatic-payment limit.",
                security_event_type="policy_allowed",
                security_event_severity="info",
            )

        # Case B: Exceeds limit -> requires human approval
        # Check if an approval already exists
        approval_obj = None
        if approval_id:
            approval_obj = (
                db.query(PaymentApproval)
                .filter(PaymentApproval.id == approval_id, PaymentApproval.bill_id == bill.id)
                .first()
            )
        else:
            # Look up latest approval for this bill
            approval_obj = (
                db.query(PaymentApproval)
                .filter(PaymentApproval.bill_id == bill.id)
                .order_by(PaymentApproval.requested_at.desc())
                .first()
            )

        if approval_obj:
            # Validate details haven't changed
            if approval_obj.details_hash != current_hash:
                approval_obj.status = "invalidated"
                approval_obj.invalidated_reason = "bill_details_changed"
                db.commit()
                return PolicyCheckResult(
                    decision="deny",
                    reason_code="approval_details_changed",
                    message="Bill details changed after approval was requested. Approval has been cancelled.",
                    approval=approval_obj,
                    security_event_type="approval_invalidated",
                    security_event_severity="warning",
                )

            # Check expiration
            expires_at = approval_obj.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now > expires_at:
                approval_obj.status = "expired"
                db.commit()
                return PolicyCheckResult(
                    decision="deny",
                    reason_code="approval_expired",
                    message="Approval has expired. A new approval must be requested.",
                    approval=approval_obj,
                    security_event_type="approval_expired",
                    security_event_severity="warning",
                )

            if approval_obj.status == "approved":
                return PolicyCheckResult(
                    decision="allow",
                    reason_code="approval_valid",
                    message="A person approved these exact details.",
                    approval=approval_obj,
                    security_event_type="policy_allowed",
                    security_event_severity="info",
                )

            if approval_obj.status == "pending":
                bill.status = "awaiting_approval"
                db.commit()
                return PolicyCheckResult(
                    decision="require_approval",
                    reason_code="amount_exceeds_limit",
                    message=(
                        "This payment exceeds the normal household limit. It requires the configured "
                        "stronger approval process before execution."
                    ),
                    approval=approval_obj,
                    security_event_type="approval_requested",
                    security_event_severity="info",
                )

        # No approval exists yet -> Create pending approval
        new_approval = PaymentApproval(
            household_id=household_id,
            bill_id=str(bill.id),
            amount=bill.amount,
            currency=bill.currency,
            destination_account_number=bill.destination_account_number,
            destination_account_number_masked=bill.destination_account_number_masked,
            destination_ifsc=bill.destination_ifsc,
            details_hash=current_hash,
            status="pending",
            reason_code="amount_exceeds_limit",
            requested_by_type=initiated_by_type,
            requested_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
        db.add(new_approval)
        bill.status = "awaiting_approval"
        db.commit()
        db.refresh(new_approval)

        return PolicyCheckResult(
            decision="require_approval",
            reason_code="amount_exceeds_limit",
            message=(
                "This payment exceeds the normal household limit. It requires the configured "
                "stronger approval process before execution."
            ),
            approval=new_approval,
            security_event_type="approval_requested",
            security_event_severity="info",
        )
