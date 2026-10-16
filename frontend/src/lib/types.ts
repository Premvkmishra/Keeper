// Types mirror the Keeper Canonical API Contract v1.0.0 exactly.

export type Money = string;
export type UUID = string;
export type Timestamp = string;
export type DateString = string;

export type MemberRole = "owner" | "caregiver" | "viewer";
export type BillerCategory =
  "electricity" | "water" | "gas" | "internet" | "phone" | "insurance" | "other";
export type BillerStatus = "active" | "suspended";
export type BeneficiaryStatus = "active" | "revoked";
export type BillStatus =
  | "received"
  | "awaiting_approval"
  | "processing"
  | "needs_review"
  | "paid"
  | "blocked"
  | "failed"
  | "cancelled";
export type BillSource = "manual" | "email_ingest" | "agent" | "demo";
export type ApprovalStatus =
  "pending" | "approved" | "rejected" | "expired" | "invalidated" | "consumed";
export type ProcessingStatus =
  "idle" | "processing" | "needs_review" | "blocked" | "paid" | "failed" | "cancelled";
export type ApprovalInvalidationReason =
  "bill_details_changed" | "beneficiary_revoked" | "biller_suspended";
export type InitiatorType = "user" | "agent";
export type Decision = "allow" | "deny" | "require_approval";
export type AttemptStatus = "requires_approval" | "blocked" | "executing" | "succeeded" | "failed";
export type ReasonCode =
  | "within_limit"
  | "approval_valid"
  | "amount_exceeds_limit"
  | "beneficiary_not_approved"
  | "biller_not_trusted"
  | "biller_suspended"
  | "bill_not_payable"
  | "already_paid"
  | "currency_mismatch"
  | "armoriq_denied"
  | "armoriq_hold"
  | "armoriq_unavailable"
  | "approval_expired"
  | "approval_details_changed"
  | "bank_error";
export type Severity = "info" | "warning" | "critical";
export type ActorType = "user" | "agent" | "system" | "witness";
export type SecurityEventType =
  | "payment_requested"
  | "policy_allowed"
  | "policy_denied"
  | "beneficiary_mismatch"
  | "biller_untrusted"
  | "approval_requested"
  | "approval_granted"
  | "approval_rejected"
  | "approval_expired"
  | "approval_invalidated"
  | "armoriq_denied"
  | "armoriq_hold"
  | "armoriq_unavailable"
  | "duplicate_blocked"
  | "payment_executed"
  | "payment_failed"
  | "mcp_tool_called"
  | "unauthorized_action_attempt"
  | "witness_verified"
  | "witness_mismatch"
  | "configuration_changed"
  | "demo_scenario_run"
  | "agent_processing_started"
  | "agent_processing_review"
  | "agent_processing_blocked"
  | "agent_processing_completed";
export type WitnessExpectedOutcome = "payment_present" | "payment_absent";
export type WitnessVerdict =
  "confirmed_paid" | "confirmed_no_payment" | "mismatch_detected" | "unverifiable";
export type DemoScenarioId = "normal_payment" | "malicious_beneficiary" | "high_value_payment";
export type StepActor = "agent" | "backend" | "armoriq" | "mock_bank" | "witness" | "human";
export type StepResult = "ok" | "blocked" | "pending" | "info";

export type ErrorCode =
  | "validation_error"
  | "unauthenticated"
  | "forbidden"
  | "demo_disabled"
  | "not_found"
  | "version_conflict"
  | "bill_not_editable"
  | "approval_not_pending"
  | "approval_expired"
  | "approval_details_changed"
  | "idempotency_conflict"
  | "duplicate_resource"
  | "dependency_unavailable"
  | "internal_error";

export interface Household {
  id: UUID;
  name: string;
  currency: string;
}

export interface Policy {
  household_id: UUID;
  auto_pay_limit: Money;
  hard_payment_limit: Money;
  currency: string;
  approval_ttl_minutes: number;
  version: number;
  updated_at: Timestamp;
  updated_by_name: string | null;
}

export interface Biller {
  id: UUID;
  name: string;
  category: BillerCategory;
  consumer_reference: string | null;
  status: BillerStatus;
  active_beneficiary_count: number;
  created_at: Timestamp;
  updated_at: Timestamp;
}

export interface Beneficiary {
  id: UUID;
  biller_id: UUID;
  biller_name: string;
  display_name: string;
  account_number_masked: string;
  ifsc: string;
  status: BeneficiaryStatus;
  created_at: Timestamp;
  revoked_at: Timestamp | null;
}

export interface Bill {
  id: UUID;
  biller_id: UUID | null;
  biller_name: string | null;
  title: string;
  category: BillerCategory;
  amount: Money;
  currency: string;
  due_date: DateString;
  status: BillStatus;
  source: BillSource;
  invoice_ref: string | null;
  destination_account_number_masked: string;
  destination_ifsc: string;
  destination_matches_approved: boolean;
  created_at: Timestamp;
  updated_at: Timestamp;
  paid_at: Timestamp | null;
}

export interface Approval {
  id: UUID;
  bill_id: UUID;
  bill_title: string;
  biller_name: string | null;
  amount: Money;
  currency: string;
  destination_account_number_masked: string;
  destination_ifsc: string;
  details_hash: string;
  status: ApprovalStatus;
  processing_status: ProcessingStatus;
  processing_message: string | null;
  reason_code: "amount_exceeds_limit";
  requested_by_type: InitiatorType;
  requested_at: Timestamp;
  expires_at: Timestamp;
  decided_at: Timestamp | null;
  decided_by_name: string | null;
  decision_note: string | null;
  invalidated_reason: ApprovalInvalidationReason | null;
}

export interface PaymentAttempt {
  id: UUID;
  bill_id: UUID;
  bill_title: string;
  approval_id: UUID | null;
  amount: Money;
  currency: string;
  destination_account_number_masked: string;
  destination_ifsc: string;
  initiated_by_type: InitiatorType;
  decision: Decision;
  status: AttemptStatus;
  reason_code: ReasonCode;
  message: string;
  bank_reference: string | null;
  created_at: Timestamp;
  completed_at: Timestamp | null;
  latest_witness_report_id: UUID | null;
}

export interface SecurityEvent {
  id: UUID;
  bill_id: UUID | null;
  attempt_id: UUID | null;
  event_type: SecurityEventType;
  severity: Severity;
  actor_type: ActorType;
  message: string;
  details: Record<string, unknown>;
  created_at: Timestamp;
}

export interface MatchedTransaction {
  bank_txn_id: string;
  amount: Money;
  currency: string;
  destination_account_number_masked: string;
  destination_ifsc: string;
  bank_status: "posted";
  created_at: Timestamp;
}

export interface WitnessReport {
  id: UUID;
  attempt_id: UUID;
  bill_id: UUID;
  expected_outcome: WitnessExpectedOutcome;
  verdict: WitnessVerdict;
  ledger_match_count: number;
  matched_transactions: MatchedTransaction[];
  summary: string;
  ledger_source: "mock_bank_sqlite";
  read_only: true;
  window_start: Timestamp;
  window_end: Timestamp;
  checked_at: Timestamp;
}

export interface PaymentOutcome {
  decision: Decision;
  reason_code: ReasonCode;
  message: string;
  idempotent_replay: boolean;
  attempt: PaymentAttempt;
  bill: Bill;
  approval: Approval | null;
  witness_report: WitnessReport | null;
}

export interface DemoStep {
  order: number;
  actor: StepActor;
  label: string;
  result: StepResult;
  detail: string;
}

export interface ListResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Health {
  status: "ok";
  database: "ok" | "down";
  mock_bank: "ok" | "down";
  armoriq: "ok" | "down" | "unconfigured";
  version: string;
}

export interface Permissions {
  can_manage_bills: boolean;
  can_approve: boolean;
  can_verify: boolean;
  can_run_demos: boolean;
  can_manage_billers: boolean;
  can_manage_policy: boolean;
}

export interface Me {
  user_id: UUID;
  email: string;
  display_name: string;
  role: MemberRole;
  household: Household;
  permissions: Permissions;
}

export interface Dashboard {
  household: Household;
  policy: { auto_pay_limit: Money; currency: string };
  counts: {
    bills_open: number;
    awaiting_approval: number;
    blocked_30d: number;
    paid_30d_count: number;
  };
  paid_30d_total: Money;
  upcoming_bills: Bill[];
  pending_approvals: Approval[];
  recent_security_events: SecurityEvent[];
  latest_witness_reports: WitnessReport[];
}

export interface BillDetail {
  bill: Bill;
  biller: Biller | null;
  approvals: Approval[];
  attempts: PaymentAttempt[];
  witness_reports: WitnessReport[];
  events: SecurityEvent[];
}

export interface ApprovalDetail {
  approval: Approval;
  bill: Bill;
  biller: Biller | null;
}

export interface PaymentDetail {
  attempt: PaymentAttempt;
  witness_reports: WitnessReport[];
  events: SecurityEvent[];
}

export interface CreateBillBody {
  title: string;
  category: BillerCategory;
  amount: Money;
  currency: "INR";
  due_date: DateString;
  invoice_ref?: string;
  biller_id?: UUID | null;
  destination_account_number: string;
  destination_ifsc: string;
}

export type UpdateBillBody = Partial<{
  title: string;
  amount: Money;
  due_date: DateString;
  biller_id: UUID | null;
  destination_account_number: string;
  destination_ifsc: string;
}>;

export interface CreateBillerBody {
  name: string;
  category: BillerCategory;
  consumer_reference?: string;
}
export type UpdateBillerBody = Partial<CreateBillerBody>;

export interface CreateBeneficiaryBody {
  biller_id: UUID;
  display_name: string;
  account_number: string;
  ifsc: string;
}

export interface UpdatePolicyBody {
  auto_pay_limit: Money;
  approval_ttl_minutes: number;
  expected_version: number;
}

export interface ExpectedResult {
  decision: Decision;
  attempt_status: AttemptStatus;
  bill_status: BillStatus;
  witness_verdict: WitnessVerdict;
}

export interface DemoScenario {
  id: DemoScenarioId;
  title: string;
  description: string;
  expected: ExpectedResult & { after_human_approval: ExpectedResult | null };
}

export interface DemoRunResult {
  scenario_id: DemoScenarioId;
  run_id: UUID;
  bill: Bill;
  outcome: PaymentOutcome;
  steps: DemoStep[];
  expected_matched: boolean;
  next_action: "none" | "approve_in_queue";
  approval_id: UUID | null;
}
