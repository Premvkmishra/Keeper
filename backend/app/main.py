import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any
import httpx
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import settings
from backend.app.core.database import Base, engine, check_db_health, SessionLocal
from backend.app.integrations.armoriq_gateway import armoriq_gateway
from backend.app.api.mcp import router as mcp_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.me import router as me_router
from backend.app.api.v1.bills import router as bills_router
from backend.app.api.v1.approvals import router as approvals_router
from backend.app.api.v1.billers import router as billers_router
from backend.app.api.v1.payments import router as payments_router
from backend.app.api.v1.policy import router as policy_router
from backend.app.api.v1.agent import router as agent_router
from backend.app.schemas.schemas import Health
from backend.app.core.seed import seed_demo_household
from backend.app.models.models import Bill, PaymentApproval, PaymentAttempt, SecurityEvent
from sqlalchemy import inspect, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("keeper")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Keeper Application...")
    if settings.APP_ENV.lower() not in ("testing", "test") and not settings.SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is required before the API can start.")
    if str(engine.url).startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        approval_columns = {column["name"] for column in inspect(engine).get_columns("payment_approvals")}
        with engine.begin() as connection:
            if "processing_status" not in approval_columns:
                connection.execute(
                    text("ALTER TABLE payment_approvals ADD COLUMN processing_status VARCHAR(20) NOT NULL DEFAULT 'idle'")
                )
            if "processing_message" not in approval_columns:
                connection.execute(text("ALTER TABLE payment_approvals ADD COLUMN processing_message VARCHAR(500)"))
            bill_columns = {column["name"] for column in inspect(engine).get_columns("bills")}
            if "processing_idempotency_key" not in bill_columns:
                connection.execute(text("ALTER TABLE bills ADD COLUMN processing_idempotency_key VARCHAR(128)"))
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_attempt_household_idempotency_idx "
                    "ON payment_attempts (household_id, idempotency_key)"
                )
            )
        db = SessionLocal()
        try:
            seed_demo_household(db)
        finally:
            db.close()
    else:
        if not inspect(engine).has_table("keeper_schema_migrations"):
            raise RuntimeError("Supabase schema is not initialized; run backend/scripts/setup_supabase.py first.")
        with engine.connect() as connection:
            current_version = connection.execute(
                text("SELECT MAX(version) FROM keeper_schema_migrations")
            ).scalar_one_or_none()
        if current_version is None or current_version < 4:
            raise RuntimeError("Supabase schema is not current; run backend/scripts/setup_supabase.py first.")

    db = SessionLocal()
    try:
        interrupted = (
            db.query(PaymentApproval)
            .filter(PaymentApproval.processing_status == "processing")
            .with_for_update()
            .all()
        )
        for approval in interrupted:
            attempt = (
                db.query(PaymentAttempt)
                .filter(
                    PaymentAttempt.household_id == approval.household_id,
                    PaymentAttempt.idempotency_key == f"approval-{approval.id}",
                )
                .first()
            )
            if attempt and attempt.status == "succeeded":
                approval.processing_status = "paid"
                approval.processing_message = "The existing payment attempt confirms success after restart."
                approval.bill.status = "paid"
                event_type = "agent_processing_completed"
            else:
                approval.processing_status = "needs_review"
                approval.processing_message = "Processing was interrupted. Reconcile payment history and the bank ledger before retrying."
                if approval.bill.status == "processing":
                    approval.bill.status = "needs_review"
                event_type = "agent_processing_review"
            db.add(
                SecurityEvent(
                    household_id=approval.household_id,
                    bill_id=approval.bill_id,
                    event_type=event_type,
                    severity="critical" if event_type == "agent_processing_review" else "info",
                    actor_type="system",
                    message=approval.processing_message,
                    details={"approval_id": str(approval.id)},
                    created_at=datetime.now(timezone.utc),
                )
            )
        if interrupted:
            db.commit()
        processing_bills = db.query(Bill).filter(Bill.status == "processing").all()
        for bill in processing_bills:
            if bill.processing_idempotency_key and db.query(PaymentAttempt).filter(
                PaymentAttempt.household_id == bill.household_id,
                PaymentAttempt.bill_id == bill.id,
                PaymentAttempt.idempotency_key == bill.processing_idempotency_key,
            ).first():
                continue
            bill.status = "needs_review"
            db.add(
                SecurityEvent(
                    household_id=bill.household_id,
                    bill_id=bill.id,
                    event_type="agent_processing_review",
                    severity="critical",
                    actor_type="system",
                    message="Bill processing was interrupted before an attempt was recorded. Review before retrying.",
                    details={"idempotency_key": bill.processing_idempotency_key},
                    created_at=datetime.now(timezone.utc),
                )
            )
        if processing_bills:
            db.commit()
    finally:
        db.close()
    logger.info("Database schema verified.")

    armoriq_gateway.initialize()
    yield
    logger.info("Shutting down Keeper Application...")
    armoriq_gateway.close()
    engine.dispose()

app = FastAPI(
    title="Keeper API",
    description="Secure, autonomous bill-payment simulation backend for older adults",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
)

# Request ID & Error Envelope Handlers
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", f"req-{uuid.uuid4().hex[:8]}")
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "internal_error")
        message = detail.get("message", "An error occurred.")
        details = detail.get("details", {})
    else:
        message = str(detail)
        code = "forbidden" if exc.status_code == 403 else "unauthenticated" if exc.status_code == 401 else "not_found" if exc.status_code == 404 else "internal_error"
        details = {}

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)
    field_errors: Dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc", [])
        field_name = str(loc[-1]) if loc else "general"
        field_errors[field_name] = err.get("msg", "Validation error")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "validation_error",
                "message": "Input validation failed.",
                "details": {"fields": field_errors},
                "request_id": request_id,
            }
        },
    )

@app.get("/health", response_model=Health, tags=["health"])
@app.get("/api/v1/health", response_model=Health, tags=["health"], include_in_schema=False)
def health_check():
    # 1. Database check
    db_ok = check_db_health()

    # 2. Mock bank check
    mock_bank_status = "down"
    try:
        bank_health_url = f"{settings.MOCK_BANK_BASE_URL.rstrip('/')}/health"
        with httpx.Client(timeout=2.0) as client:
            res = client.get(bank_health_url)
            if res.status_code == 200 and res.json().get("status") == "ok":
                mock_bank_status = "ok"
    except Exception:
        mock_bank_status = "down"

    # 3. ArmorIQ check
    armoriq_status = armoriq_gateway.is_healthy()

    return Health(
        status="ok",
        database="ok" if db_ok else "down",
        mock_bank=mock_bank_status,
        armoriq=armoriq_status,
        version="1.0.0",
    )

# API v1 Router Registration
api_v1_prefix = "/api/v1"
app.include_router(auth_router, prefix=api_v1_prefix)
app.include_router(me_router, prefix=api_v1_prefix)
app.include_router(bills_router, prefix=api_v1_prefix)
app.include_router(approvals_router, prefix=api_v1_prefix)
app.include_router(billers_router, prefix=api_v1_prefix)
app.include_router(payments_router, prefix=api_v1_prefix)
app.include_router(policy_router, prefix=api_v1_prefix)
app.include_router(agent_router, prefix=api_v1_prefix)

# MCP Tool Authorization Route
app.include_router(mcp_router)
