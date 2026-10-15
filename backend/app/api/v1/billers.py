from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.core.database import get_db
from backend.app.security.auth import (
    AuthenticatedUser,
    get_current_user,
    require_manage_billers,
)
from backend.app.models.models import TrustedBiller, ApprovedBeneficiary, PaymentApproval
from backend.app.schemas.schemas import (
    Biller as BillerSchema,
    Beneficiary as BeneficiarySchema,
    CreateBillerBody,
    UpdateBillerBody,
    CreateBeneficiaryBody,
    ListResponse,
)

router = APIRouter(tags=["billers_beneficiaries"])

def mask_account(num: str) -> str:
    if len(num) <= 4:
        return f"••••{num}"
    return f"••••••••{num[-4:]}"

def biller_to_dict(b: TrustedBiller, db: Session) -> dict:
    active_count = (
        db.query(func.count(ApprovedBeneficiary.id))
        .filter(ApprovedBeneficiary.biller_id == b.id, ApprovedBeneficiary.status == "active")
        .scalar()
        or 0
    )
    return {
        "id": str(b.id),
        "name": b.name,
        "category": b.category,
        "consumer_reference": b.consumer_reference,
        "status": b.status,
        "active_beneficiary_count": active_count,
        "created_at": b.created_at.isoformat(),
        "updated_at": b.updated_at.isoformat(),
    }

def ben_to_dict(ben: ApprovedBeneficiary) -> dict:
    return {
        "id": str(ben.id),
        "biller_id": str(ben.biller_id),
        "biller_name": ben.biller.name if ben.biller else "Unknown",
        "display_name": ben.display_name,
        "account_number_masked": ben.account_number_masked,
        "ifsc": ben.ifsc,
        "status": ben.status,
        "created_at": ben.created_at.isoformat(),
        "revoked_at": ben.revoked_at.isoformat() if ben.revoked_at else None,
    }

# Billers
@router.get("/billers", response_model=ListResponse[BillerSchema])
def list_billers(
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(TrustedBiller).filter(TrustedBiller.household_id == user.household_id)
    total = query.count()
    billers = query.order_by(TrustedBiller.name.asc()).offset(offset).limit(limit).all()
    return ListResponse(
        items=[biller_to_dict(b, db) for b in billers],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.post("/billers", response_model=BillerSchema, status_code=status.HTTP_201_CREATED)
def create_biller(
    body: CreateBillerBody,
    user: AuthenticatedUser = Depends(require_manage_billers),
    db: Session = Depends(get_db),
):
    biller = TrustedBiller(
        household_id=user.household_id,
        name=body.name,
        category=body.category,
        consumer_reference=body.consumer_reference,
        status="active",
    )
    db.add(biller)
    db.commit()
    db.refresh(biller)
    return biller_to_dict(biller, db)

@router.patch("/billers/{biller_id}", response_model=BillerSchema)
def update_biller(
    biller_id: str,
    body: UpdateBillerBody,
    user: AuthenticatedUser = Depends(require_manage_billers),
    db: Session = Depends(get_db),
):
    b = db.query(TrustedBiller).filter(TrustedBiller.id == biller_id, TrustedBiller.household_id == user.household_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Biller not found.")
    if body.name is not None:
        b.name = body.name
    if body.category is not None:
        b.category = body.category
    if body.consumer_reference is not None:
        b.consumer_reference = body.consumer_reference
    b.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(b)
    return biller_to_dict(b, db)

@router.post("/billers/{biller_id}/suspend", response_model=BillerSchema)
def suspend_biller(
    biller_id: str,
    user: AuthenticatedUser = Depends(require_manage_billers),
    db: Session = Depends(get_db),
):
    b = db.query(TrustedBiller).filter(TrustedBiller.id == biller_id, TrustedBiller.household_id == user.household_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Biller not found.")
    b.status = "suspended"
    b.updated_at = datetime.now(timezone.utc)

    # Invalidate approvals for bills belonging to this biller
    for bill in b.bills:
        for appr in bill.approvals:
            if appr.status == "pending":
                appr.status = "invalidated"
                appr.invalidated_reason = "biller_suspended"

    db.commit()
    db.refresh(b)
    return biller_to_dict(b, db)

@router.post("/billers/{biller_id}/reactivate", response_model=BillerSchema)
def reactivate_biller(
    biller_id: str,
    user: AuthenticatedUser = Depends(require_manage_billers),
    db: Session = Depends(get_db),
):
    b = db.query(TrustedBiller).filter(TrustedBiller.id == biller_id, TrustedBiller.household_id == user.household_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Biller not found.")
    b.status = "active"
    b.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(b)
    return biller_to_dict(b, db)

# Beneficiaries
@router.get("/beneficiaries", response_model=ListResponse[BeneficiarySchema])
def list_beneficiaries(
    biller_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(ApprovedBeneficiary).filter(ApprovedBeneficiary.household_id == user.household_id)
    if biller_id:
        query = query.filter(ApprovedBeneficiary.biller_id == biller_id)
    if status:
        query = query.filter(ApprovedBeneficiary.status == status)

    total = query.count()
    bens = query.order_by(ApprovedBeneficiary.display_name.asc()).offset(offset).limit(limit).all()

    return ListResponse(
        items=[ben_to_dict(b) for b in bens],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.post("/beneficiaries", response_model=BeneficiarySchema, status_code=status.HTTP_201_CREATED)
def create_beneficiary(
    body: CreateBeneficiaryBody,
    user: AuthenticatedUser = Depends(require_manage_billers),
    db: Session = Depends(get_db),
):
    # Verify biller exists in this household
    biller = db.query(TrustedBiller).filter(TrustedBiller.id == body.biller_id, TrustedBiller.household_id == user.household_id).first()
    if not biller:
        raise HTTPException(status_code=404, detail="Biller not found.")

    masked = mask_account(body.account_number)
    ben = ApprovedBeneficiary(
        household_id=user.household_id,
        biller_id=str(body.biller_id),
        display_name=body.display_name,
        account_number=body.account_number,
        account_number_masked=masked,
        ifsc=body.ifsc,
        status="active",
    )
    db.add(ben)
    db.commit()
    db.refresh(ben)
    return ben_to_dict(ben)

@router.post("/beneficiaries/{ben_id}/revoke", response_model=BeneficiarySchema)
def revoke_beneficiary(
    ben_id: str,
    user: AuthenticatedUser = Depends(require_manage_billers),
    db: Session = Depends(get_db),
):
    ben = db.query(ApprovedBeneficiary).filter(ApprovedBeneficiary.id == ben_id, ApprovedBeneficiary.household_id == user.household_id).first()
    if not ben:
        raise HTTPException(status_code=404, detail="Beneficiary not found.")

    ben.status = "revoked"
    ben.revoked_at = datetime.now(timezone.utc)

    # Invalidate approvals targeting this beneficiary
    approvals = (
        db.query(PaymentApproval)
        .filter(
            PaymentApproval.household_id == user.household_id,
            PaymentApproval.destination_account_number == ben.account_number,
            PaymentApproval.destination_ifsc == ben.ifsc,
            PaymentApproval.status == "pending",
        )
        .all()
    )
    for a in approvals:
        a.status = "invalidated"
        a.invalidated_reason = "beneficiary_revoked"

    db.commit()
    db.refresh(ben)
    return ben_to_dict(ben)
