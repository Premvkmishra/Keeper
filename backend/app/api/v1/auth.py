import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.seed import DEMO_ADMIN_EMAIL, DEMO_ADMIN_USER_ID, seed_demo_household
from backend.app.models.models import Household, HouseholdMember, HouseholdPolicy, User
from backend.app.security.auth import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
)
from backend.app.security.passwords import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (at least 8 characters)")
    confirm_password: str = Field(..., min_length=8, description="Confirmation password")
    display_name: Optional[str] = Field(None, max_length=120, description="Optional display name")


class LoginRequest(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: str = Field(..., min_length=1)


class UserSummary(BaseModel):
    user_id: str
    email: str
    display_name: str
    role: str
    household: dict


class AuthResponse(BaseModel):
    token: str
    user: UserSummary


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()

    if not EMAIL_REGEX.match(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "Invalid email address format.",
                "details": {"fields": {"email": "Please enter a valid email address."}},
            },
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "Password must be at least 8 characters long.",
                "details": {"fields": {"password": "Password must be at least 8 characters long."}},
            },
        )

    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_error",
                "message": "Passwords do not match.",
                "details": {"fields": {"confirm_password": "Passwords do not match."}},
            },
        )

    # Check for duplicate user
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "duplicate_resource",
                "message": "An account with this email address already exists.",
                "details": {"fields": {"email": "An account with this email already exists."}},
            },
        )

    existing_member = db.query(HouseholdMember).filter(HouseholdMember.email == email).first()
    if existing_member and db.query(User).filter(User.id == existing_member.user_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "duplicate_resource",
                "message": "An account with this email address already exists.",
                "details": {"fields": {"email": "An account with this email already exists."}},
            },
        )

    display_name = (payload.display_name or "").strip()
    if not display_name:
        display_name = email.split("@")[0].replace(".", " ").replace("_", " ").title()

    # Create User
    new_user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=display_name,
    )
    db.add(new_user)
    db.flush()

    # Link to existing household if invited, or create a new dedicated household
    household = None
    if existing_member:
        household = db.query(Household).filter(Household.id == existing_member.household_id).first()
        existing_member.user_id = str(new_user.id)
        existing_member.display_name = display_name
        role = existing_member.role
    else:
        household = Household(
            name=f"{display_name}'s Household",
            currency="INR",
        )
        db.add(household)
        db.flush()

        policy = HouseholdPolicy(
            household_id=household.id,
            auto_pay_limit=10000.00,
            currency="INR",
            approval_ttl_minutes=1440,
            version=1,
            updated_by_name=display_name,
        )
        db.add(policy)

        role = "owner"
        member = HouseholdMember(
            household_id=household.id,
            user_id=str(new_user.id),
            email=email,
            display_name=display_name,
            role=role,
        )
        db.add(member)

    db.commit()

    token = create_access_token(
        user_id=str(new_user.id),
        email=email,
        role=role,
        household_id=str(household.id),
    )

    return {
        "token": token,
        "user": {
            "user_id": str(new_user.id),
            "email": email,
            "display_name": display_name,
            "role": role,
            "household": {
                "id": str(household.id),
                "name": household.name,
                "currency": household.currency,
            },
        },
    }


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    identifier = (payload.email or payload.username or "").strip().lower()
    password = payload.password or ""

    # 1. Check demo admin backwards compatibility
    if identifier == settings.DEMO_ADMIN_USERNAME.lower() and password == settings.DEMO_ADMIN_PASSWORD:
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

        token = create_access_token(
            user_id=DEMO_ADMIN_USER_ID,
            email=DEMO_ADMIN_EMAIL,
            role="owner",
            household_id=str(household.id),
        )
        return {
            "token": token,
            "user": {
                "user_id": DEMO_ADMIN_USER_ID,
                "email": DEMO_ADMIN_EMAIL,
                "display_name": member.display_name,
                "role": "owner",
                "household": {"id": str(household.id), "name": household.name, "currency": household.currency},
            },
        }

    # 2. Authenticate against registered users
    user = db.query(User).filter(User.email == identifier).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Invalid email or password."},
        )

    # Resolve household membership
    member = db.query(HouseholdMember).filter(HouseholdMember.user_id == str(user.id)).first()
    if not member:
        member = db.query(HouseholdMember).filter(HouseholdMember.email == user.email).first()
        if member:
            member.user_id = str(user.id)
            db.commit()

    if not member:
        # Create user household if somehow missing
        household = Household(name=f"{user.display_name}'s Household", currency="INR")
        db.add(household)
        db.flush()
        policy = HouseholdPolicy(
            household_id=household.id,
            auto_pay_limit=10000.00,
            currency="INR",
            approval_ttl_minutes=1440,
            version=1,
            updated_by_name=user.display_name,
        )
        db.add(policy)
        member = HouseholdMember(
            household_id=household.id,
            user_id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role="owner",
        )
        db.add(member)
        db.commit()
    else:
        household = db.query(Household).filter(Household.id == member.household_id).first()

    token = create_access_token(
        user_id=str(user.id),
        email=user.email,
        role=member.role,
        household_id=str(household.id),
    )

    return {
        "token": token,
        "user": {
            "user_id": str(user.id),
            "email": user.email,
            "display_name": member.display_name,
            "role": member.role,
            "household": {
                "id": str(household.id),
                "name": household.name,
                "currency": household.currency,
            },
        },
    }


@router.post("/logout")
def logout():
    return {"message": "Successfully signed out."}


@router.get("/me")
def auth_me(user: AuthenticatedUser = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "household": {
            "id": str(user.household.id),
            "name": user.household.name,
            "currency": user.household.currency,
        },
        "permissions": user.permissions.model_dump(),
    }
