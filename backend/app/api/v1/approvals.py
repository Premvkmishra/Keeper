import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.security.auth import (
    AuthenticatedUser,
    get_current_user,
    require_approve,
)
from backend.app.models.models import (
    PaymentApproval,
    Bill,
    TrustedBiller,
    ApprovedBeneficiary,
    PaymentAttempt,
    SecurityEvent,
    WitnessReportModel,
)
from backend.app.schemas.schemas import (
    Approval as ApprovalSchema,
    ApprovalDetail,
    ApproveBody,
    RejectBody,
    PaymentOutcome,
    ListResponse,
)
from backend.app.services.agent_service import processing_configuration_blockers, run_approved_payment

router = APIRouter(prefix="/approvals", tags=["approvals"])

def approval_to_dict(a: PaymentApproval) -> dict:
    return {
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
        "processing_status": a.processing_status,
        "processing_message": a.processing_message,
        "reason_code": a.reason_code,
        "requested_by_type": a.requested_by_type,
        "requested_at": a.requested_at.isoformat(),
        "expires_at": a.expires_at.isoformat(),
        "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        "decided_by_name": a.decided_by_name,
        "decision_note": a.decision_note,
        "invalidated_reason": a.invalidated_reason,
    }

@router.get("", response_model=ListResponse[ApprovalSchema])
def list_approvals(
    status: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(PaymentApproval).filter(PaymentApproval.household_id == user.household_id)
    if status:
        query = query.filter(PaymentApproval.status == status)

    total = query.count()
    apprs = query.order_by(PaymentApproval.requested_at.desc()).offset(offset).limit(limit).all()

    return ListResponse(
        items=[approval_to_dict(a) for a in apprs],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.get("/{approval_id}", response_model=ApprovalDetail)
def get_approval(
    approval_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    appr = (
        db.query(PaymentApproval)
        .filter(PaymentApproval.id == approval_id, PaymentApproval.household_id == user.household_id)
        .first()
    )
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found.")

    bill = appr.bill
    biller_data = None
    if bill and bill.biller:
        b = bill.biller
        active_count = (
            db.query(func.count(ApprovedBeneficiary.id))
            .filter(ApprovedBeneficiary.biller_id == b.id, ApprovedBeneficiary.status == "active")
            .scalar()
            or 0
        )
        biller_data = {
            "id": str(b.id),
            "name": b.name,
            "category": b.category,
            "consumer_reference": b.consumer_reference,
            "status": b.status,
            "active_beneficiary_count": active_count,
            "created_at": b.created_at.isoformat(),
            "updated_at": b.updated_at.isoformat(),
        }

    bill_data = {
        "id": str(bill.id),
        "biller_id": str(bill.biller_id) if bill.biller_id else None,
        "biller_name": bill.biller.name if bill.biller else None,
        "title": bill.title,
        "category": bill.category,
        "amount": f"{float(bill.amount):.2f}",
        "currency": bill.currency,
        "due_date": str(bill.due_date),
        "status": bill.status,
        "source": bill.source,
        "invoice_ref": bill.invoice_ref,
        "destination_account_number_masked": bill.destination_account_number_masked,
        "destination_ifsc": bill.destination_ifsc,
        "destination_matches_approved": bill.destination_matches_approved,
        "created_at": bill.created_at.isoformat(),
        "updated_at": bill.updated_at.isoformat(),
        "paid_at": bill.paid_at.isoformat() if bill.paid_at else None,
    }

    return ApprovalDetail(
        approval=approval_to_dict(appr),
        bill=bill_data,
        biller=biller_data,
    )

@router.post("/{approval_id}/approve", response_model=ApprovalSchema)
def approve_payment(
    approval_id: str,
    body: ApproveBody,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(require_approve),
    db: Session = Depends(get_db),
):
    appr = (
        db.query(PaymentApproval)
        .filter(PaymentApproval.id == approval_id, PaymentApproval.household_id == user.household_id)
        .with_for_update()
        .first()
    )
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found.")

    if appr.status == "approved" and appr.processing_status != "idle":
        return approval_to_dict(appr)

    if appr.status != "pending":
        raise HTTPException(
            status_code=400,
            detail={"code": "approval_not_pending", "message": f"Approval is not pending (status: {appr.status})."},
        )

    now = datetime.now(timezone.utc)
    expires_at = appr.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now > expires_at:
        appr.status = "expired"
        db.commit()
        raise HTTPException(
            status_code=400,
            detail={"code": "approval_expired", "message": "Approval has expired."},
        )

    if body.details_hash != appr.details_hash:
        appr.status = "invalidated"
        appr.invalidated_reason = "bill_details_changed"
        db.commit()
        raise HTTPException(
            status_code=400,
            detail={"code": "approval_details_changed", "message": "Bill details changed after approval was requested."},
        )

    blockers = processing_configuration_blockers()
    appr.status = "approved"
    appr.decided_at = now
    appr.decided_by_user_id = user.user_id
    appr.decided_by_name = user.display_name
    appr.decision_note = body.note
    appr.processing_status = "needs_review" if blockers else "processing"
    appr.processing_message = (
        "Processing stopped: " + "; ".join(blockers) + "."
        if blockers
        else "Human approval recorded. Gemini is reviewing the bill before the payment tool is requested."
    )
    appr.bill.status = "needs_review" if blockers else "processing"
    appr.bill.processing_idempotency_key = None if blockers else f"approval-{appr.id}"

    db.add(SecurityEvent(
        household_id=user.household_id,
        bill_id=appr.bill_id,
        event_type="approval_granted",
        severity="info",
        actor_type="user",
        message=f"Human approval granted by {user.display_name}.",
        details={"approval_id": str(appr.id), "note": body.note},
        created_at=now,
    ))
    db.add(
        SecurityEvent(
            household_id=user.household_id,
            bill_id=appr.bill_id,
            event_type="agent_processing_review" if blockers else "agent_processing_started",
            severity="critical" if blockers else "info",
            actor_type="system" if blockers else "agent",
            message=appr.processing_message,
            details={"approval_id": str(appr.id), "missing_configuration": blockers},
            created_at=now,
        )
    )
    db.commit()
    db.refresh(appr)

    if not blockers:
        background_tasks.add_task(run_approved_payment, str(appr.id), user.email)

    return approval_to_dict(appr)

@router.post("/{approval_id}/retry", response_model=ApprovalSchema)
def retry_payment_processing(
    approval_id: str,
    background_tasks: BackgroundTasks,
    user: AuthenticatedUser = Depends(require_approve),
    db: Session = Depends(get_db),
):
    appr = (
        db.query(PaymentApproval)
        .filter(PaymentApproval.id == approval_id, PaymentApproval.household_id == user.household_id)
        .with_for_update()
        .first()
    )
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found.")
    if appr.status != "approved":
        raise HTTPException(status_code=409, detail="Only an approved payment can be resumed.")
    if appr.processing_status == "processing":
        return approval_to_dict(appr)
    if appr.processing_status != "needs_review":
        raise HTTPException(status_code=409, detail="This payment is not waiting for processing review.")

    base_idempotency_key = f"approval-{appr.id}"
    existing_attempt = (
        db.query(PaymentAttempt)
        .filter(
            PaymentAttempt.household_id == user.household_id,
            PaymentAttempt.idempotency_key == base_idempotency_key,
        )
        .first()
    )
    idempotency_key = base_idempotency_key
    if existing_attempt:
        report = (
            db.query(WitnessReportModel)
            .filter(WitnessReportModel.id == existing_attempt.latest_witness_report_id)
            .first()
            if existing_attempt.latest_witness_report_id
            else None
        )
        if existing_attempt.status != "failed" or not report or report.verdict != "confirmed_no_payment":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_conflict",
                    "message": "An attempt exists without verified ledger absence. Reconcile before retrying.",
                },
            )
        attempt_count = (
            db.query(PaymentAttempt)
            .join(WitnessReportModel, PaymentAttempt.latest_witness_report_id == WitnessReportModel.id)
            .filter(
                PaymentAttempt.household_id == user.household_id,
                PaymentAttempt.approval_id == appr.id,
                WitnessReportModel.verdict == "confirmed_no_payment",
            )
            .count()
        )
        idempotency_key = f"{base_idempotency_key}-retry-{attempt_count}"

    blockers = processing_configuration_blockers()
    now = datetime.now(timezone.utc)
    if blockers:
        appr.processing_message = "Processing stopped: " + "; ".join(blockers) + "."
        db.add(
            SecurityEvent(
                household_id=user.household_id,
                bill_id=appr.bill_id,
                event_type="agent_processing_review",
                severity="critical",
                actor_type="system",
                message=appr.processing_message,
                details={"approval_id": str(appr.id), "missing_configuration": blockers},
                created_at=now,
            )
        )
        db.commit()
        db.refresh(appr)
        return approval_to_dict(appr)

    appr.processing_status = "processing"
    appr.processing_message = "Review cleared. Gemini is checking the approved bill before requesting its payment."
    appr.bill.status = "processing"
    appr.bill.processing_idempotency_key = idempotency_key
    db.add(
        SecurityEvent(
            household_id=user.household_id,
            bill_id=appr.bill_id,
            event_type="agent_processing_started",
            severity="info",
            actor_type="agent",
            message=appr.processing_message,
            details={"approval_id": str(appr.id)},
            created_at=now,
        )
    )
    db.commit()
    db.refresh(appr)
    background_tasks.add_task(run_approved_payment, str(appr.id), user.email, idempotency_key)
    return approval_to_dict(appr)

@router.post("/{approval_id}/reject", response_model=ApprovalSchema)
def reject_approval(
    approval_id: str,
    body: RejectBody,
    user: AuthenticatedUser = Depends(require_approve),
    db: Session = Depends(get_db),
):
    appr = (
        db.query(PaymentApproval)
        .filter(PaymentApproval.id == approval_id, PaymentApproval.household_id == user.household_id)
        .first()
    )
    if not appr:
        raise HTTPException(status_code=404, detail="Approval not found.")

    if appr.status != "pending":
        raise HTTPException(
            status_code=400,
            detail={"code": "approval_not_pending", "message": f"Approval is not pending (status: {appr.status})."},
        )

    now = datetime.now(timezone.utc)
    appr.status = "rejected"
    appr.decided_at = now
    appr.decided_by_user_id = user.user_id
    appr.decided_by_name = user.display_name
    appr.decision_note = body.note

    if appr.bill:
        appr.bill.status = "received"

    db.commit()

    sec_event = SecurityEvent(
        household_id=user.household_id,
        bill_id=appr.bill_id,
        event_type="approval_rejected",
        severity="info",
        actor_type="user",
        message=f"Human approval declined by {user.display_name}.",
        details={"approval_id": str(appr.id), "note": body.note},
        created_at=now,
    )
    db.add(sec_event)
    db.commit()

    return approval_to_dict(appr)
