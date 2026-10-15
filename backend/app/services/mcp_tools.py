"""MCP tool handlers with signed backend-owned household context."""
import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.models import Bill, PaymentAttempt, SecurityEvent
from backend.app.services.payment_execution import PaymentExecutionService


def create_authorization_context(household_id: str, user_email: str) -> str:
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        raise RuntimeError("SUPABASE_JWT_SECRET is required to authorize MCP context.")
    payload = json.dumps(
        {"household_id": str(household_id), "user_email": user_email, "issued_at": int(time.time())},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def resolve_authorization_context(token: str) -> str:
    secret = settings.SUPABASE_JWT_SECRET
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(
            (secret or "").encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not secret or not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid signature")
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        issued_at = int(payload["issued_at"])
        household_id = str(payload["household_id"])
        user_email = payload["user_email"]
        age = int(time.time()) - issued_at
        if not user_email or not household_id or age < -5 or age > 120:
            raise ValueError("expired or invalid claims")
        return household_id
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired MCP authorization context.") from exc


class ListBillsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorization_context: str = Field(..., min_length=1, max_length=2048)
    status: Optional[str] = None


class GetBillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorization_context: str = Field(..., min_length=1, max_length=2048)
    bill_id: str = Field(..., min_length=1, max_length=64)


class ProposePaymentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorization_context: str = Field(..., min_length=1, max_length=2048)
    bill_id: str = Field(..., min_length=1, max_length=64)
    idempotency_key: str = Field(..., min_length=1, max_length=128)


class GetPaymentStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authorization_context: str = Field(..., min_length=1, max_length=2048)
    attempt_id: Optional[str] = None
    bill_id: Optional[str] = None


ALLOWED_TOOLS = ("list_bills", "get_bill", "propose_payment", "get_payment_status")


def execute_tool(db: Session, household_id: str, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name not in ALLOWED_TOOLS:
        raise HTTPException(status_code=400, detail="Unknown tool name.")

    safe_arguments = {key: value for key, value in arguments.items() if key != "authorization_context"}
    event = SecurityEvent(
        household_id=household_id,
        event_type="mcp_tool_called",
        severity="info",
        actor_type="agent",
        message=f"MCP tool '{name}' called with signed household context.",
        details={"tool_name": name, "arguments": safe_arguments, "decided_by": "mcp_context"},
    )
    db.add(event)
    db.commit()

    if name == "list_bills":
        parsed = ListBillsInput(**arguments)
        query = db.query(Bill).filter(Bill.household_id == household_id)
        if parsed.status:
            query = query.filter(Bill.status == parsed.status)
        bills = query.limit(50).all()
        return {
            "bills": [
                {
                    "id": str(b.id),
                    "title": b.title,
                    "amount": f"{float(b.amount):.2f}",
                    "currency": b.currency,
                    "due_date": str(b.due_date),
                    "status": b.status,
                    "destination_account_masked": b.destination_account_number_masked,
                    "destination_ifsc": b.destination_ifsc,
                }
                for b in bills
            ]
        }

    if name == "get_bill":
        parsed = GetBillInput(**arguments)
        b = db.query(Bill).filter(Bill.id == parsed.bill_id, Bill.household_id == household_id).first()
        if not b:
            raise HTTPException(status_code=404, detail=f"Bill {parsed.bill_id} not found.")
        return {
            "id": str(b.id),
            "title": b.title,
            "category": b.category,
            "amount": f"{float(b.amount):.2f}",
            "currency": b.currency,
            "due_date": str(b.due_date),
            "status": b.status,
            "destination_account_masked": b.destination_account_number_masked,
            "destination_ifsc": b.destination_ifsc,
            "destination_matches_approved": b.destination_matches_approved,
            "invoice_ref": b.invoice_ref,
        }

    if name == "propose_payment":
        parsed = ProposePaymentInput(**arguments)
        b = db.query(Bill).filter(Bill.id == parsed.bill_id, Bill.household_id == household_id).first()
        if not b:
            raise HTTPException(status_code=404, detail=f"Bill {parsed.bill_id} not found.")
        payment_svc = PaymentExecutionService()
        _attempt, outcome = payment_svc.execute_payment(
            db=db,
            bill=b,
            household_id=household_id,
            idempotency_key=parsed.idempotency_key,
            initiated_by_type="agent",
        )
        return outcome.model_dump()

    parsed = GetPaymentStatusInput(**arguments)
    if parsed.attempt_id:
        att = db.query(PaymentAttempt).filter(
            PaymentAttempt.id == parsed.attempt_id,
            PaymentAttempt.household_id == household_id,
        ).first()
        if not att:
            raise HTTPException(status_code=404, detail="Payment attempt not found.")
        return {
            "attempt_id": str(att.id),
            "bill_id": str(att.bill_id),
            "status": att.status,
            "decision": att.decision,
            "reason_code": att.reason_code,
            "bank_reference": att.bank_reference,
            "message": att.message,
        }
    if parsed.bill_id:
        b = db.query(Bill).filter(Bill.id == parsed.bill_id, Bill.household_id == household_id).first()
        if not b:
            raise HTTPException(status_code=404, detail="Bill not found.")
        return {"bill_id": str(b.id), "status": b.status, "paid_at": str(b.paid_at) if b.paid_at else None}
    raise HTTPException(status_code=400, detail="Must provide either attempt_id or bill_id.")
