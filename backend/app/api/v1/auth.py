from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_USER_ID, seed_demo_household
from backend.app.models.models import Household, HouseholdMember
from backend.app.security.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


def _issue_demo_admin_token() -> str:
    payload = {
        "sub": DEMO_ADMIN_USER_ID,
        "email": DEMO_ADMIN_EMAIL,
        "role": "owner",
        "household_id": "00000000-0000-0000-0000-000000000001",
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    }
    return jwt.encode(payload, settings.DEMO_ADMIN_JWT_SECRET, algorithm="HS256")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = (payload.username or "").strip()
    password = payload.password or ""

    if username != settings.DEMO_ADMIN_USERNAME or password != settings.DEMO_ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Invalid username or password."},
        )

    seed_demo_household(db)

    household = db.query(Household).filter(Household.id == settings.MCP_AGENT_HOUSEHOLD_ID).first()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "dependency_unavailable", "message": "Demo household seed is missing."},
        )

    member = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household.id, HouseholdMember.email == DEMO_ADMIN_EMAIL)
        .first()
    )
    if not member:
        member = HouseholdMember(
            household_id=household.id,
            user_id=DEMO_ADMIN_USER_ID,
            email=DEMO_ADMIN_EMAIL,
            display_name="System Admin",
            role="owner",
        )
        db.add(member)
        db.commit()

    token = _issue_demo_admin_token()
    return {
        "token": token,
        "user": {
            "user_id": DEMO_ADMIN_USER_ID,
            "email": DEMO_ADMIN_EMAIL,
            "display_name": "System Admin",
            "role": "owner",
            "household": {"id": household.id, "name": household.name, "currency": household.currency},
        },
    }


@router.get("/me")
def auth_me(user: AuthenticatedUser = Depends(get_current_user)):
    return {"user_id": user.user_id, "email": user.email, "display_name": user.display_name, "role": user.role}
