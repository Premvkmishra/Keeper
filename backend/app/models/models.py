import uuid
from datetime import datetime, timezone, date
from typing import Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    LargeBinary,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
    text,
)
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type.
    Uses PostgreSQL native UUID type, otherwise uses CHAR(36).
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


def gen_uuid_str() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class Household(Base):
    __tablename__ = "households"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    name = Column(String(255), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    members = relationship("HouseholdMember", back_populates="household", cascade="all, delete-orphan")
    policy = relationship("HouseholdPolicy", back_populates="household", uselist=False, cascade="all, delete-orphan")
    billers = relationship("TrustedBiller", back_populates="household", cascade="all, delete-orphan")
    bills = relationship("Bill", back_populates="household", cascade="all, delete-orphan")
    approvals = relationship("PaymentApproval", back_populates="household", cascade="all, delete-orphan")
    attempts = relationship("PaymentAttempt", back_populates="household", cascade="all, delete-orphan")
    security_events = relationship("SecurityEvent", back_populates="household", cascade="all, delete-orphan")
    witness_reports = relationship("WitnessReportModel", back_populates="household", cascade="all, delete-orphan")


class HouseholdMember(Base):
    __tablename__ = "household_members"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(GUID, nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # "owner", "caregiver", "viewer"
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    household = relationship("Household", back_populates="members")
    __table_args__ = (UniqueConstraint("household_id", "user_id", name="uq_household_member_user"),)

class HouseholdPolicy(Base):
    __tablename__ = "household_policies"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, unique=True)
    auto_pay_limit = Column(Numeric(12, 2), nullable=False, default=10000.00)
    currency = Column(String(3), nullable=False, default="INR")
    approval_ttl_minutes = Column(Integer, nullable=False, default=1440)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    updated_by_user_id = Column(GUID, nullable=True)
    updated_by_name = Column(String(255), nullable=True)

    household = relationship("Household", back_populates="policy")


class TrustedBiller(Base):
    __tablename__ = "trusted_billers"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(20), nullable=False)
    consumer_reference = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # "active", "suspended"
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    household = relationship("Household", back_populates="billers")
    beneficiaries = relationship("ApprovedBeneficiary", back_populates="biller", cascade="all, delete-orphan")
    bills = relationship("Bill", back_populates="biller")


class ApprovedBeneficiary(Base):
    __tablename__ = "approved_beneficiaries"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    biller_id = Column(GUID, ForeignKey("trusted_billers.id", ondelete="CASCADE"), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    account_number = Column(String(64), nullable=False)
    account_number_masked = Column(String(64), nullable=False)
    ifsc = Column(String(11), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # "active", "revoked"
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    biller = relationship("TrustedBiller", back_populates="beneficiaries")


class Bill(Base):
    __tablename__ = "bills"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    biller_id = Column(GUID, ForeignKey("trusted_billers.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    category = Column(String(20), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    due_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="received")  # received, awaiting_approval, processing, needs_review, paid, blocked, failed, cancelled
    source = Column(String(20), nullable=False, default="manual")  # "manual", "email_ingest", "agent", "demo"
    invoice_ref = Column(String(64), nullable=True)
    destination_account_number = Column(String(64), nullable=False)
    destination_account_number_masked = Column(String(64), nullable=False)
    destination_ifsc = Column(String(11), nullable=False)
    destination_matches_approved = Column(Boolean, nullable=False, default=False)
    processing_idempotency_key = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    household = relationship("Household", back_populates="bills")
    biller = relationship("TrustedBiller", back_populates="bills")
    approvals = relationship("PaymentApproval", back_populates="bill", cascade="all, delete-orphan")
    attempts = relationship("PaymentAttempt", back_populates="bill", cascade="all, delete-orphan")
    document = relationship("BillDocument", back_populates="bill", uselist=False, cascade="all, delete-orphan")


class BillDocument(Base):
    __tablename__ = "bill_documents"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id = Column(GUID, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, unique=True)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    sha256 = Column(String(64), nullable=False)
    content = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    bill = relationship("Bill", back_populates="document")


class PaymentApproval(Base):
    __tablename__ = "payment_approvals"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id = Column(GUID, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    destination_account_number = Column(String(64), nullable=False)
    destination_account_number_masked = Column(String(64), nullable=False)
    destination_ifsc = Column(String(11), nullable=False)
    details_hash = Column(String(128), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # "pending", "approved", "rejected", "expired", "invalidated", "consumed"
    processing_status = Column(String(20), nullable=False, default="idle")
    processing_message = Column(String(500), nullable=True)
    reason_code = Column(String(40), nullable=False, default="amount_exceeds_limit")
    requested_by_type = Column(String(20), nullable=False)  # "agent", "user"
    requested_by_user_id = Column(GUID, nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by_user_id = Column(GUID, nullable=True)
    decided_by_name = Column(String(255), nullable=True)
    decision_note = Column(String(500), nullable=True)
    invalidated_reason = Column(String(40), nullable=True)

    household = relationship("Household", back_populates="approvals")
    bill = relationship("Bill", back_populates="approvals")


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id = Column(GUID, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    approval_id = Column(GUID, ForeignKey("payment_approvals.id", ondelete="SET NULL"), nullable=True)
    idempotency_key = Column(String(128), nullable=False, index=True)
    client_reference = Column(String(128), nullable=False, unique=True, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    destination_account_number = Column(String(64), nullable=False)
    destination_account_number_masked = Column(String(64), nullable=False)
    destination_ifsc = Column(String(11), nullable=False)
    initiated_by_type = Column(String(20), nullable=False)  # "agent", "user"
    initiated_by_user_id = Column(GUID, nullable=True)
    decision = Column(String(20), nullable=False)  # "allow", "deny", "require_approval"
    status = Column(String(20), nullable=False)  # "requires_approval", "blocked", "executing", "succeeded", "failed"
    reason_code = Column(String(40), nullable=False)
    message = Column(String(255), nullable=False)
    bank_reference = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    latest_witness_report_id = Column(
        GUID,
        ForeignKey("witness_reports.id", ondelete="SET NULL", use_alter=True, name="fk_payment_attempts_witness_report"),
        nullable=True,
    )

    household = relationship("Household", back_populates="attempts")
    bill = relationship("Bill", back_populates="attempts")
    __table_args__ = (UniqueConstraint("household_id", "idempotency_key", name="uq_attempt_household_idempotency"),)


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id = Column(GUID, ForeignKey("bills.id", ondelete="SET NULL"), nullable=True)
    attempt_id = Column(GUID, ForeignKey("payment_attempts.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)  # "info", "warning", "critical"
    actor_type = Column(String(20), nullable=False)  # "user", "agent", "system", "witness"
    message = Column(String(500), nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    household = relationship("Household", back_populates="security_events")


class WitnessReportModel(Base):
    __tablename__ = "witness_reports"

    id = Column(GUID, primary_key=True, default=gen_uuid_str)
    household_id = Column(GUID, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_id = Column(GUID, ForeignKey("payment_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    bill_id = Column(GUID, ForeignKey("bills.id", ondelete="CASCADE"), nullable=False, index=True)
    expected_outcome = Column(String(30), nullable=False)
    verdict = Column(String(30), nullable=False)
    ledger_match_count = Column(Integer, nullable=False, default=0)
    matched_transactions = Column(JSON, nullable=False, default=list)
    summary = Column(String(500), nullable=False)
    ledger_source = Column(String(30), nullable=False, default="mock_bank_sqlite")
    read_only = Column(Boolean, nullable=False, default=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    checked_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    household = relationship("Household", back_populates="witness_reports")
