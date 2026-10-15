from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.security.auth import AuthenticatedUser, get_current_user
from backend.app.models.models import (
    Bill,
    PaymentApproval,
    PaymentAttempt,
    SecurityEvent,
    WitnessReportModel,
    HouseholdPolicy,
)
from backend.app.schemas.schemas import Me, Dashboard, Household

router = APIRouter(tags=["me_dashboard"])

@router.get("/me", response_model=Me)
def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    return Me(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        household=Household(
            id=str(user.household.id),
            name=user.household.name,
            currency=user.household.currency,
        ),
        permissions=user.permissions,
    )

@router.get("/dashboard", response_model=Dashboard)
def get_dashboard(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hid = user.household_id
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Policy
    pol = db.query(HouseholdPolicy).filter(HouseholdPolicy.household_id == hid).first()
    limit_str = f"{float(pol.auto_pay_limit):.2f}" if pol else "10000.00"
    pol_dict = {"auto_pay_limit": limit_str, "currency": pol.currency if pol else "INR"}

    # Counts
    bills_open = (
        db.query(func.count(Bill.id))
        .filter(Bill.household_id == hid, Bill.status.in_(
            ["received", "awaiting_approval", "processing", "needs_review"]
        ))
        .scalar()
        or 0
    )
    awaiting_approval = (
        db.query(func.count(PaymentApproval.id))
        .filter(PaymentApproval.household_id == hid, PaymentApproval.status == "pending")
        .scalar()
        or 0
    )
    blocked_30d = (
        db.query(func.count(PaymentAttempt.id))
        .filter(
            PaymentAttempt.household_id == hid,
            PaymentAttempt.status == "blocked",
            PaymentAttempt.created_at >= thirty_days_ago,
        )
        .scalar()
        or 0
    )
    paid_30d_count = (
        db.query(func.count(PaymentAttempt.id))
        .filter(
            PaymentAttempt.household_id == hid,
            PaymentAttempt.status == "succeeded",
            PaymentAttempt.created_at >= thirty_days_ago,
        )
        .scalar()
        or 0
    )

    # Paid 30d total
    paid_sum = (
        db.query(func.sum(PaymentAttempt.amount))
        .filter(
            PaymentAttempt.household_id == hid,
            PaymentAttempt.status == "succeeded",
            PaymentAttempt.created_at >= thirty_days_ago,
        )
        .scalar()
    )
    paid_30d_total = f"{float(paid_sum):.2f}" if paid_sum else "0.00"

    # Open bills include any payment awaiting processing or review.
    upcoming = (
        db.query(Bill)
        .filter(Bill.household_id == hid, Bill.status.in_(
            ["received", "awaiting_approval", "processing", "needs_review"]
        ))
        .order_by(Bill.due_date.asc())
        .limit(10)
        .all()
    )

    # Pending approvals
    pending_apprs = (
        db.query(PaymentApproval)
        .filter(PaymentApproval.household_id == hid, PaymentApproval.status == "pending")
        .order_by(PaymentApproval.requested_at.desc())
        .limit(10)
        .all()
    )

    # Recent security events
    recent_events = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.household_id == hid)
        .order_by(SecurityEvent.created_at.desc())
        .limit(10)
        .all()
    )

    # Latest witness reports
    latest_witness = (
        db.query(WitnessReportModel)
        .filter(WitnessReportModel.household_id == hid)
        .order_by(WitnessReportModel.checked_at.desc())
        .limit(10)
        .all()
    )

    return Dashboard(
        household=Household(
            id=str(user.household.id),
            name=user.household.name,
            currency=user.household.currency,
        ),
        policy=pol_dict,
        counts={
            "bills_open": bills_open,
            "awaiting_approval": awaiting_approval,
            "blocked_30d": blocked_30d,
            "paid_30d_count": paid_30d_count,
        },
        paid_30d_total=paid_30d_total,
        upcoming_bills=[
            {
                "id": str(b.id),
                "biller_id": str(b.biller_id) if b.biller_id else None,
                "biller_name": b.biller.name if b.biller else None,
                "title": b.title,
                "category": b.category,
                "amount": f"{float(b.amount):.2f}",
                "currency": b.currency,
                "due_date": str(b.due_date),
                "status": b.status,
                "source": b.source,
                "invoice_ref": b.invoice_ref,
                "destination_account_number_masked": b.destination_account_number_masked,
                "destination_ifsc": b.destination_ifsc,
                "destination_matches_approved": b.destination_matches_approved,
                "created_at": b.created_at.isoformat(),
                "updated_at": b.updated_at.isoformat(),
                "paid_at": b.paid_at.isoformat() if b.paid_at else None,
            }
            for b in upcoming
        ],
        pending_approvals=[
            {
                "id": str(a.id),
                "bill_id": str(a.bill_id),
                "bill_title": a.bill.title if a.bill else "Bill",
                "biller_name": a.bill.biller.name if a.bill and a.bill.biller else None,
                "amount": f"{float(a.amount):.2f}",
                "currency": a.currency,
                "destination_account_number_masked": a.destination_account_number_masked,
                "destination_ifsc": a.destination_ifsc,
                "details_hash": a.details_hash,
                "status": a.status,
                "reason_code": a.reason_code,
                "requested_by_type": a.requested_by_type,
                "requested_at": a.requested_at.isoformat(),
                "expires_at": a.expires_at.isoformat(),
                "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                "decided_by_name": a.decided_by_name,
                "decision_note": a.decision_note,
                "invalidated_reason": a.invalidated_reason,
            }
            for a in pending_apprs
        ],
        recent_security_events=[
            {
                "id": str(e.id),
                "bill_id": str(e.bill_id) if e.bill_id else None,
                "attempt_id": str(e.attempt_id) if e.attempt_id else None,
                "event_type": e.event_type,
                "severity": e.severity,
                "actor_type": e.actor_type,
                "message": e.message,
                "details": e.details or {},
                "created_at": e.created_at.isoformat(),
            }
            for e in recent_events
        ],
        latest_witness_reports=[
            {
                "id": str(w.id),
                "attempt_id": str(w.attempt_id),
                "bill_id": str(w.bill_id),
                "expected_outcome": w.expected_outcome,
                "verdict": w.verdict,
                "ledger_match_count": w.ledger_match_count,
                "matched_transactions": w.matched_transactions or [],
                "summary": w.summary,
                "ledger_source": w.ledger_source,
                "read_only": True,
                "window_start": w.window_start.isoformat(),
                "window_end": w.window_end.isoformat(),
                "checked_at": w.checked_at.isoformat(),
            }
            for w in latest_witness
        ],
    )
