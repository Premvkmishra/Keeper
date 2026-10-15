from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.models import Household, HouseholdMember, HouseholdPolicy
from backend.app.security.auth import AuthenticatedUser, decode_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class HouseholdBootstrapRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    household_name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)


def _membership_response(member: HouseholdMember) -> dict:
    household = member.household
    if not household:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "household_unavailable", "message": "The account's household is unavailable."},
        )
    return {
        "user_id": member.user_id,
        "email": member.email,
        "display_name": member.display_name,
        "role": member.role,
        "household": {"id": household.id, "name": household.name, "currency": household.currency},
    }


@router.post("/household")
def bootstrap_household(
    body: HouseholdBootstrapRequest,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "A valid Supabase access token is required."},
        )
    claims = decode_token(authorization.split(" ", 1)[1].strip())
    user_id = claims.get("sub")
    email = claims.get("email")
    if not isinstance(user_id, str) or not user_id or not isinstance(email, str) or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Access token is missing user identity claims."},
        )

    member = db.query(HouseholdMember).filter(HouseholdMember.user_id == user_id).first()
    if member:
        return _membership_response(member)

    member = db.query(HouseholdMember).filter(HouseholdMember.email == email).first()
    if member:
        member.user_id = user_id
        db.commit()
        db.refresh(member)
        return _membership_response(member)

    household = Household(name=body.household_name, currency="INR")
    db.add(household)
    db.flush()
    member = HouseholdMember(
        household_id=household.id,
        user_id=user_id,
        email=email,
        display_name=body.display_name,
        role="owner",
    )
    db.add(member)
    db.add(
        HouseholdPolicy(
            household_id=household.id,
            auto_pay_limit=10000.00,
            currency="INR",
            approval_ttl_minutes=1440,
            version=1,
            updated_by_user_id=user_id,
            updated_by_name=body.display_name,
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(HouseholdMember).filter(HouseholdMember.user_id == user_id).first()
        if existing:
            return _membership_response(existing)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "household_setup_conflict", "message": "Household setup conflicted; please retry."},
        ) from exc
    db.refresh(member)
    return _membership_response(member)


@router.get("/me")
def auth_me(user: AuthenticatedUser = Depends(get_current_user)):
    return {"user_id": user.user_id, "email": user.email, "display_name": user.display_name, "role": user.role}
