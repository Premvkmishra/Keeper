from datetime import datetime, date
from typing import Dict, Generic, List, Literal, Optional, TypeVar, Any
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")

# Basic types
Money = str
UUID = str
Timestamp = str
DateString = str

MemberRole = Literal["owner", "caregiver", "viewer"]
BillerCategory = Literal["electricity", "water", "gas", "internet", "phone", "insurance", "other"]
BillerStatus = Literal["active", "suspended"]
BeneficiaryStatus = Literal["active", "revoked"]
BillStatus = Literal["received", "awaiting_approval", "processing", "needs_review", "paid", "blocked", "failed", "cancelled"]
BillSource = Literal["manual", "email_ingest", "agent", "demo"]
ApprovalStatus = Literal["pending", "approved", "rejected", "expired", "invalidated", "consumed"]
ProcessingStatus = Literal["idle", "processing", "needs_review", "blocked", "paid", "failed", "cancelled"]
ApprovalInvalidationReason = Literal["bill_details_changed", "beneficiary_revoked", "biller_suspended"]
InitiatorType = Literal["user", "agent"]
Decision = Literal["allow", "deny", "require_approval"]
AttemptStatus = Literal["requires_approval", "blocked", "executing", "succeeded", "failed"]
ReasonCode = Literal[
    "within_limit",
    "approval_valid",
    "amount_exceeds_limit",
    "beneficiary_not_approved",
    "biller_not_trusted",
    "biller_suspended",
    "bill_not_payable",
    "already_paid",
    "currency_mismatch",
    "armoriq_denied",
    "armoriq_hold",
    "armoriq_unavailable",
    "approval_expired",
    "approval_details_changed",
    "bank_error",
]
Severity = Literal["info", "warning", "critical"]
ActorType = Literal["user", "agent", "system", "witness"]
SecurityEventType = Literal[
    "payment_requested",
    "policy_allowed",
    "policy_denied",
    "beneficiary_mismatch",
    "biller_untrusted",
    "approval_requested",
    "approval_granted",
    "approval_rejected",
    "approval_expired",
    "approval_invalidated",
    "armoriq_denied",
    "armoriq_hold",
    "armoriq_unavailable",
    "duplicate_blocked",
    "payment_executed",
    "payment_failed",
    "mcp_tool_called",
    "unauthorized_action_attempt",
    "witness_verified",
    "witness_mismatch",
    "configuration_changed",
    "demo_scenario_run",
    "agent_processing_started",
    "agent_processing_review",
    "agent_processing_blocked",
    "agent_processing_completed",
]
WitnessExpectedOutcome = Literal["payment_present", "payment_absent"]
WitnessVerdict = Literal["confirmed_paid", "confirmed_no_payment", "mismatch_detected", "unverifiable"]
DemoScenarioId = Literal["normal_payment", "malicious_beneficiary", "high_value_payment"]
StepActor = Literal["agent", "backend", "armoriq", "mock_bank", "witness", "human"]
StepResult = Literal["ok", "blocked", "pending", "info"]

ErrorCode = Literal[
    "validation_error",
    "unauthenticated",
    "forbidden",
    "demo_disabled",
    "not_found",
    "version_conflict",
    "bill_not_editable",
    "approval_not_pending",
    "approval_expired",
    "approval_details_changed",
    "idempotency_conflict",
    "duplicate_resource",
    "dependency_unavailable",
    "idempotency_conflict",
    "internal_error",
]

# Error Envelope
class ApiErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    request_id: Optional[str] = None

class ErrorResponse(BaseModel):
    error: ApiErrorDetail

# Response Schemas
class Household(BaseModel):
    id: UUID
    name: str
    currency: str

    model_config = ConfigDict(from_attributes=True)

class Policy(BaseModel):
    household_id: UUID
    auto_pay_limit: Money
    hard_payment_limit: Money
    currency: str
    approval_ttl_minutes: int
    version: int
    updated_at: Timestamp
    updated_by_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class Permissions(BaseModel):
    can_manage_bills: bool
    can_approve: bool
    can_verify: bool
    can_run_demos: bool
    can_manage_billers: bool
    can_manage_policy: bool

class Me(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    role: MemberRole
    household: Household
    permissions: Permissions

class Health(BaseModel):
    status: Literal["ok"]
    database: Literal["ok", "down"]
    mock_bank: Literal["ok", "down"]
    armoriq: Literal["ok", "down", "unconfigured"]
    version: str

class Biller(BaseModel):
    id: UUID
    name: str
    category: BillerCategory
    consumer_reference: Optional[str] = None
    status: BillerStatus
    active_beneficiary_count: int
    created_at: Timestamp
    updated_at: Timestamp

    model_config = ConfigDict(from_attributes=True)

class Beneficiary(BaseModel):
    id: UUID
    biller_id: UUID
    biller_name: str
    display_name: str
    account_number_masked: str
    ifsc: str
    status: BeneficiaryStatus
    created_at: Timestamp
    revoked_at: Optional[Timestamp] = None

    model_config = ConfigDict(from_attributes=True)

class Bill(BaseModel):
    id: UUID
    biller_id: Optional[UUID] = None
    biller_name: Optional[str] = None
    title: str
    category: BillerCategory
    amount: Money
    currency: str
    due_date: DateString
    status: BillStatus
    source: BillSource
    invoice_ref: Optional[str] = None
    destination_account_number_masked: str
    destination_ifsc: str
    destination_matches_approved: bool
    created_at: Timestamp
    updated_at: Timestamp
    paid_at: Optional[Timestamp] = None

    model_config = ConfigDict(from_attributes=True)

class Approval(BaseModel):
    id: UUID
    bill_id: UUID
    bill_title: str
    biller_name: Optional[str] = None
    amount: Money
    currency: str
    destination_account_number_masked: str
    destination_ifsc: str
    details_hash: str
    status: ApprovalStatus
    processing_status: ProcessingStatus = "idle"
    processing_message: Optional[str] = None
    reason_code: Literal["amount_exceeds_limit"]
    requested_by_type: InitiatorType
    requested_at: Timestamp
    expires_at: Timestamp
    decided_at: Optional[Timestamp] = None
    decided_by_name: Optional[str] = None
    decision_note: Optional[str] = None
    invalidated_reason: Optional[ApprovalInvalidationReason] = None

    model_config = ConfigDict(from_attributes=True)

class PaymentAttempt(BaseModel):
    id: UUID
    bill_id: UUID
    bill_title: str
    approval_id: Optional[UUID] = None
    amount: Money
    currency: str
    destination_account_number_masked: str
    destination_ifsc: str
    initiated_by_type: InitiatorType
    decision: Decision
    status: AttemptStatus
    reason_code: ReasonCode
    message: str
    bank_reference: Optional[str] = None
    created_at: Timestamp
    completed_at: Optional[Timestamp] = None
    latest_witness_report_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)

class SecurityEvent(BaseModel):
    id: UUID
    bill_id: Optional[UUID] = None
    attempt_id: Optional[UUID] = None
    event_type: SecurityEventType
    severity: Severity
    actor_type: ActorType
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: Timestamp

    model_config = ConfigDict(from_attributes=True)

class MatchedTransaction(BaseModel):
    bank_txn_id: str
    amount: Money
    currency: str
    destination_account_number_masked: str
    destination_ifsc: str
    bank_status: Literal["posted"]
    created_at: Timestamp

class WitnessReport(BaseModel):
    id: UUID
    attempt_id: UUID
    bill_id: UUID
    expected_outcome: WitnessExpectedOutcome
    verdict: WitnessVerdict
    ledger_match_count: int
    matched_transactions: List[MatchedTransaction]
    summary: str
    ledger_source: Literal["mock_bank_sqlite"] = "mock_bank_sqlite"
    read_only: Literal[True] = True
    window_start: Timestamp
    window_end: Timestamp
    checked_at: Timestamp

    model_config = ConfigDict(from_attributes=True)

class PaymentOutcome(BaseModel):
    decision: Decision
    reason_code: ReasonCode
    message: str
    idempotent_replay: bool
    attempt: PaymentAttempt
    bill: Bill
    approval: Optional[Approval] = None
    witness_report: Optional[WitnessReport] = None

class BillDetail(BaseModel):
    bill: Bill
    biller: Optional[Biller] = None
    approvals: List[Approval]
    attempts: List[PaymentAttempt]
    witness_reports: List[WitnessReport]
    events: List[SecurityEvent]

class ApprovalDetail(BaseModel):
    approval: Approval
    bill: Bill
    biller: Optional[Biller] = None

class PaymentDetail(BaseModel):
    attempt: PaymentAttempt
    witness_reports: List[WitnessReport]
    events: List[SecurityEvent]

class Dashboard(BaseModel):
    household: Household
    policy: Dict[str, str]  # { auto_pay_limit: Money, currency: str }
    counts: Dict[str, int]  # { bills_open: int, awaiting_approval: int, blocked_30d: int, paid_30d_count: int }
    paid_30d_total: Money
    upcoming_bills: List[Bill]
    pending_approvals: List[Approval]
    recent_security_events: List[SecurityEvent]
    latest_witness_reports: List[WitnessReport]

class ListResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int

# Request Bodies
class CreateBillBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    category: BillerCategory
    amount: Money
    currency: Literal["INR"] = "INR"
    due_date: DateString
    invoice_ref: Optional[str] = Field(None, max_length=64)
    biller_id: Optional[UUID] = None
    destination_account_number: str = Field(..., min_length=6, max_length=34)
    destination_ifsc: str = Field(..., min_length=11, max_length=11)

class UpdateBillBody(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=120)
    amount: Optional[Money] = None
    due_date: Optional[DateString] = None
    biller_id: Optional[UUID] = None
    destination_account_number: Optional[str] = Field(None, min_length=6, max_length=34)
    destination_ifsc: Optional[str] = Field(None, min_length=11, max_length=11)

class PayBillBody(BaseModel):
    idempotency_key: str = Field(..., min_length=1, max_length=128)

class ApproveBody(BaseModel):
    details_hash: str = Field(..., min_length=1, max_length=128)
    note: Optional[str] = Field(None, max_length=500)

class RejectBody(BaseModel):
    note: Optional[str] = Field(None, max_length=500)

class CreateBillerBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    category: BillerCategory
    consumer_reference: Optional[str] = Field(None, max_length=64)

class UpdateBillerBody(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    category: Optional[BillerCategory] = None
    consumer_reference: Optional[str] = Field(None, max_length=64)

class CreateBeneficiaryBody(BaseModel):
    biller_id: UUID
    display_name: str = Field(..., min_length=1, max_length=120)
    account_number: str = Field(..., min_length=6, max_length=34)
    ifsc: str = Field(..., min_length=11, max_length=11)

class UpdatePolicyBody(BaseModel):
    auto_pay_limit: Money
    approval_ttl_minutes: int = Field(..., ge=5, le=10080)
    expected_version: int

# Demo Scenarios
class ExpectedResult(BaseModel):
    decision: Decision
    attempt_status: AttemptStatus
    bill_status: BillStatus
    witness_verdict: WitnessVerdict

class DemoScenario(BaseModel):
    id: DemoScenarioId
    title: str
    description: str
    expected: ExpectedResult
    after_human_approval: Optional[ExpectedResult] = None

class DemoStep(BaseModel):
    order: int
    actor: StepActor
    label: str
    result: StepResult
    detail: str

class DemoRunResult(BaseModel):
    scenario_id: DemoScenarioId
    run_id: UUID
    bill: Bill
    outcome: PaymentOutcome
    steps: List[DemoStep]
    expected_matched: bool
    next_action: Literal["none", "approve_in_queue"]
    approval_id: Optional[UUID] = None
