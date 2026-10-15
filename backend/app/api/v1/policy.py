from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.security.auth import (
    AuthenticatedUser,
    get_current_user,
    require_manage_policy,
)
from backend.app.models.models import HouseholdPolicy, SecurityEvent
from backend.app.schemas.schemas import Policy as PolicySchema, UpdatePolicyBody
from backend.app.core.config import settings

router = APIRouter(prefix="/policy", tags=["policy"])

def policy_to_dict(p: HouseholdPolicy) -> dict:
    return {
        "household_id": str(p.household_id),
        "auto_pay_limit": f"{float(p.auto_pay_limit):.2f}",
        "hard_payment_limit": f"{settings.HARD_PAYMENT_LIMIT:.2f}",
        "currency": p.currency,
        "approval_ttl_minutes": p.approval_ttl_minutes,
        "version": p.version,
        "updated_at": p.updated_at.isoformat(),
        "updated_by_name": p.updated_by_name,
    }

@router.get("", response_model=PolicySchema)
def get_policy(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = db.query(HouseholdPolicy).filter(HouseholdPolicy.household_id == user.household_id).first()
    if not p:
        p = HouseholdPolicy(
            household_id=user.household_id,
            auto_pay_limit=10000.00,
            currency="INR",
            approval_ttl_minutes=1440,
            version=1,
            updated_by_name=user.display_name,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
    return policy_to_dict(p)

@router.put("", response_model=PolicySchema)
def update_policy(
    body: UpdatePolicyBody,
    user: AuthenticatedUser = Depends(require_manage_policy),
    db: Session = Depends(get_db),
):
    p = db.query(HouseholdPolicy).filter(HouseholdPolicy.household_id == user.household_id).first()
    if not p:
        p = HouseholdPolicy(
            household_id=user.household_id,
            auto_pay_limit=float(body.auto_pay_limit),
            currency="INR",
            approval_ttl_minutes=body.approval_ttl_minutes,
            version=1,
            updated_by_name=user.display_name,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return policy_to_dict(p)

    if body.expected_version != p.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "version_conflict",
                "message": "Someone else changed these limits. Please reload the latest values.",
                "details": {"current_version": p.version, "expected_version": body.expected_version},
            },
        )

    now = datetime.now(timezone.utc)
    old_limit = p.auto_pay_limit
    old_ttl = p.approval_ttl_minutes

    p.auto_pay_limit = float(body.auto_pay_limit)
    p.approval_ttl_minutes = body.approval_ttl_minutes
    p.version += 1
    p.updated_at = now
    p.updated_by_user_id = user.user_id
    p.updated_by_name = user.display_name

    sec_event = SecurityEvent(
        household_id=user.household_id,
        event_type="configuration_changed",
        severity="info",
        actor_type="user",
        message=f"Safety limits updated by {user.display_name}.",
        details={
            "old_limit": str(old_limit),
            "new_limit": body.auto_pay_limit,
            "old_ttl": old_ttl,
            "new_ttl": body.approval_ttl_minutes,
            "version": p.version,
        },
        created_at=now,
    )
    db.add(sec_event)
    db.commit()
    db.refresh(p)
    return policy_to_dict(p)
