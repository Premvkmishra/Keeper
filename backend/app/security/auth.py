import base64
import json
import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import Depends, Header, HTTPException, status
import jwt
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.models import HouseholdMember, Household
from backend.app.schemas.schemas import Permissions, MemberRole

logger = logging.getLogger(__name__)

class AuthenticatedUser:
    def __init__(
        self,
        user_id: str,
        email: str,
        display_name: str,
        role: MemberRole,
        household_id: str,
        household: Household,
    ):
        self.user_id = user_id
        self.email = email
        self.display_name = display_name
        self.role = role
        self.household_id = household_id
        self.household = household

    @property
    def permissions(self) -> Permissions:
        is_owner = self.role == "owner"
        is_caregiver = self.role in ("owner", "caregiver")
        return Permissions(
            can_manage_bills=is_caregiver,
            can_approve=is_caregiver,
            can_verify=True,
            can_run_demos=is_caregiver,
            can_manage_billers=is_owner,
            can_manage_policy=is_owner,
        )

def decode_token(token: str) -> Dict[str, Any]:
    """Verify a Supabase JWT via JWKS or accept the local demo admin JWT."""
    try:
        return jwt.decode(
            token,
            settings.DEMO_ADMIN_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError:
        pass

    if not settings.SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "dependency_unavailable",
                "message": "SUPABASE_JWT_SECRET is not configured; authentication is unavailable.",
            },
        )
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError:
        try:
            if not settings.SUPABASE_URL:
                raise ValueError("missing supabase url")
            jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
            jwks_client = PyJWKClient(jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                options={"verify_aud": False},
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "unauthenticated", "message": f"Invalid token: {str(e)}"},
            )

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Missing or invalid Authorization header."},
        )

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token)

    # Supabase JWT contains 'sub' as user_id and 'email'
    user_id = payload.get("sub") or payload.get("user_id")
    email = payload.get("email") or "unknown@user.com"

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Token missing user identifier."},
        )

    # Lookup household membership
    member = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.user_id == str(user_id))
        .first()
    )

    if not member:
        # Check by email as a fallback for initial invites or demo accounts
        member = (
            db.query(HouseholdMember)
            .filter(HouseholdMember.email == email)
            .first()
        )
        if member:
            # Associate this user_id with the existing member row
            member.user_id = str(user_id)
            db.commit()
            db.refresh(member)

    if not member:
        # User is authenticated in Supabase but not assigned to any household yet
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "forbidden",
                "message": "Account is not assigned to any household yet.",
                "details": {"reason": "no_household_membership"},
            },
        )

    household = db.query(Household).filter(Household.id == member.household_id).first()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "forbidden",
                "message": "Associated household not found.",
                "details": {"reason": "no_household_membership"},
            },
        )

    return AuthenticatedUser(
        user_id=str(member.user_id),
        email=member.email,
        display_name=member.display_name,
        role=member.role,
        household_id=str(member.household_id),
        household=household,
    )

def require_manage_bills(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.permissions.can_manage_bills:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Only owner or caregiver can manage bills."},
        )
    return user

def require_approve(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.permissions.can_approve:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Only owner or caregiver can approve payments."},
        )
    return user

def require_manage_billers(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.permissions.can_manage_billers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Only the household owner can manage trusted billers."},
        )
    return user

def require_manage_policy(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.permissions.can_manage_policy:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Only the household owner can change safety limits."},
        )
    return user

def require_run_demos(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    if not user.permissions.can_run_demos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "forbidden", "message": "Only owner or caregiver can run demo scenarios."},
        )
    return user
