from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.security.auth import AuthenticatedUser, get_current_user
from backend.app.models.models import PaymentAttempt, WitnessReportModel, SecurityEvent, Bill
from backend.app.schemas.schemas import (
    PaymentAttempt as PaymentAttemptSchema,
    PaymentDetail,
    SecurityEvent as SecurityEventSchema,
    WitnessReport as WitnessReportSchema,
    ListResponse,
)
from backend.app.services.witness_service import WitnessService

router = APIRouter(tags=["payments_security_witness"])

def attempt_to_dict(at: PaymentAttempt) -> dict:
    return {
        "id": str(at.id),
        "bill_id": str(at.bill_id),
        "bill_title": at.bill.title if at.bill else "Bill",
        "approval_id": str(at.approval_id) if at.approval_id else None,
        "amount": f"{float(at.amount):.2f}",
        "currency": at.currency,
        "destination_account_number_masked": at.destination_account_number_masked,
        "destination_ifsc": at.destination_ifsc,
        "initiated_by_type": at.initiated_by_type,
        "decision": at.decision,
        "status": at.status,
        "reason_code": at.reason_code,
        "message": at.message,
        "bank_reference": at.bank_reference,
        "created_at": at.created_at.isoformat(),
        "completed_at": at.completed_at.isoformat() if at.completed_at else None,
        "latest_witness_report_id": str(at.latest_witness_report_id) if at.latest_witness_report_id else None,
    }

def witness_to_dict(w: WitnessReportModel) -> dict:
    return {
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

def event_to_dict(e: SecurityEvent) -> dict:
    return {
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

# Payments
@router.get("/payments", response_model=ListResponse[PaymentAttemptSchema])
def list_payments(
    status: Optional[str] = Query(None),
    bill_id: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(PaymentAttempt).filter(PaymentAttempt.household_id == user.household_id)
    if status:
        query = query.filter(PaymentAttempt.status == status)
    if bill_id:
        query = query.filter(PaymentAttempt.bill_id == bill_id)

    total = query.count()
    attempts = query.order_by(PaymentAttempt.created_at.desc()).offset(offset).limit(limit).all()

    return ListResponse(
        items=[attempt_to_dict(a) for a in attempts],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.get("/payments/{attempt_id}", response_model=PaymentDetail)
def get_payment(
    attempt_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    at = (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.id == attempt_id, PaymentAttempt.household_id == user.household_id)
        .first()
    )
    if not at:
        raise HTTPException(status_code=404, detail="Payment attempt not found.")

    witness_reports = (
        db.query(WitnessReportModel)
        .filter(WitnessReportModel.attempt_id == at.id)
        .order_by(WitnessReportModel.checked_at.desc())
        .all()
    )

    events = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.attempt_id == at.id)
        .order_by(SecurityEvent.created_at.desc())
        .all()
    )

    return PaymentDetail(
        attempt=attempt_to_dict(at),
        witness_reports=[witness_to_dict(w) for w in witness_reports],
        events=[event_to_dict(e) for e in events],
    )

@router.post("/payments/{attempt_id}/witness-verify", response_model=WitnessReportSchema)
def witness_verify(
    attempt_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    at = (
        db.query(PaymentAttempt)
        .filter(PaymentAttempt.id == attempt_id, PaymentAttempt.household_id == user.household_id)
        .first()
    )
    if not at:
        raise HTTPException(status_code=404, detail="Payment attempt not found.")

    svc = WitnessService()
    rep = svc.verify_and_record(
        db=db,
        attempt=at,
        expected_destination_account=at.destination_account_number,
    )
    return witness_to_dict(rep)

# Security Events
@router.get("/security-events", response_model=ListResponse[SecurityEventSchema])
def list_security_events(
    severity: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    bill_id: Optional[str] = Query(None),
    attempt_id: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(SecurityEvent).filter(SecurityEvent.household_id == user.household_id)
    if severity:
        query = query.filter(SecurityEvent.severity == severity)
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    if bill_id:
        query = query.filter(SecurityEvent.bill_id == bill_id)
    if attempt_id:
        query = query.filter(SecurityEvent.attempt_id == attempt_id)

    total = query.count()
    events = query.order_by(SecurityEvent.created_at.desc()).offset(offset).limit(limit).all()

    return ListResponse(
        items=[event_to_dict(e) for e in events],
        total=total,
        limit=limit,
        offset=offset,
    )

# Witness Reports
@router.get("/witness-reports", response_model=ListResponse[WitnessReportSchema])
def list_witness_reports(
    verdict: Optional[str] = Query(None),
    bill_id: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(WitnessReportModel).filter(WitnessReportModel.household_id == user.household_id)
    if verdict:
        query = query.filter(WitnessReportModel.verdict == verdict)
    if bill_id:
        query = query.filter(WitnessReportModel.bill_id == bill_id)

    total = query.count()
    reports = query.order_by(WitnessReportModel.checked_at.desc()).offset(offset).limit(limit).all()

    return ListResponse(
        items=[witness_to_dict(w) for w in reports],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.get("/witness-reports/{report_id}", response_model=WitnessReportSchema)
def get_witness_report(
    report_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rep = (
        db.query(WitnessReportModel)
        .filter(WitnessReportModel.id == report_id, WitnessReportModel.household_id == user.household_id)
        .first()
    )
    if not rep:
        raise HTTPException(status_code=404, detail="Witness report not found.")
    return witness_to_dict(rep)
