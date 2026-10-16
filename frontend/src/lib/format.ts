import type {
  ApprovalInvalidationReason,
  ApprovalStatus,
  AttemptStatus,
  ProcessingStatus,
  BeneficiaryStatus,
  BillerCategory,
  BillerStatus,
  BillSource,
  BillStatus,
  Decision,
  MemberRole,
  ReasonCode,
  SecurityEventType,
  Severity,
  StepActor,
  StepResult,
  WitnessExpectedOutcome,
  WitnessVerdict,
} from "./types";

export type Tone = "info" | "warning" | "success" | "danger" | "muted";
export interface Label {
  label: string;
  tone: Tone;
}

export const BILL_STATUS: Record<BillStatus, Label> = {
  received: { label: "Ready to pay", tone: "info" },
  awaiting_approval: { label: "Needs your approval", tone: "warning" },
  processing: { label: "Processing", tone: "info" },
  needs_review: { label: "Needs review", tone: "warning" },
  paid: { label: "Paid", tone: "success" },
  blocked: { label: "Blocked for safety", tone: "danger" },
  failed: { label: "Payment failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "muted" },
};

export const ATTEMPT_STATUS: Record<AttemptStatus, Label> = {
  requires_approval: { label: "Waiting for approval", tone: "warning" },
  blocked: { label: "Blocked", tone: "danger" },
  executing: { label: "Processing", tone: "info" },
  succeeded: { label: "Bank processed it", tone: "success" },
  failed: { label: "Bank error", tone: "danger" },
};

export const DECISION: Record<Decision, Label> = {
  allow: { label: "Allowed", tone: "success" },
  deny: { label: "Denied", tone: "danger" },
  require_approval: { label: "Needs a person", tone: "warning" },
};

export const APPROVAL_STATUS: Record<ApprovalStatus, Label> = {
  pending: { label: "Waiting", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Declined", tone: "muted" },
  expired: { label: "Expired", tone: "muted" },
  invalidated: { label: "Cancelled — details changed", tone: "muted" },
  consumed: { label: "Used", tone: "success" },
};

export const PROCESSING_STATUS: Record<ProcessingStatus, Label> = {
  idle: { label: "Not started", tone: "muted" },
  processing: { label: "Processing", tone: "info" },
  needs_review: { label: "Needs review", tone: "warning" },
  blocked: { label: "Blocked", tone: "danger" },
  paid: { label: "Paid", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "muted" },
};

export const WITNESS_VERDICT: Record<WitnessVerdict, Label> = {
  confirmed_paid: { label: "Witness confirms: payment found in bank ledger", tone: "success" },
  confirmed_no_payment: { label: "Witness confirms: no payment in bank ledger", tone: "info" },
  mismatch_detected: { label: "Witness found a mismatch", tone: "danger" },
  unverifiable: { label: "Witness could not check", tone: "warning" },
};

export const SEVERITY: Record<Severity, Label> = {
  info: { label: "Info", tone: "info" },
  warning: { label: "Warning", tone: "warning" },
  critical: { label: "Critical", tone: "danger" },
};

export const REASON_CODE: Record<ReasonCode, string> = {
  within_limit: "Within your automatic-payment limit",
  approval_valid: "A person approved these exact details",
  amount_exceeds_limit: "Above your automatic-payment limit",
  beneficiary_not_approved: "Payee account is not on your approved list",
  biller_not_trusted: "Biller is not on your trusted list",
  biller_suspended: "Biller is paused",
  bill_not_payable: "This bill can't be paid right now",
  already_paid: "This bill was already paid",
  currency_mismatch: "Currency does not match",
  armoriq_denied: "Security guard denied the action",
  armoriq_hold: "Security guard placed the action on hold for review",
  armoriq_unavailable: "Security guard unavailable — payment stopped to stay safe",
  approval_expired: "Approval expired",
  approval_details_changed: "Details changed after approval",
  bank_error: "The bank reported an error",
};

export const MEMBER_ROLE: Record<MemberRole, string> = {
  owner: "Owner",
  caregiver: "Caregiver",
  viewer: "Viewer",
};

export const BILLER_CATEGORY: Record<BillerCategory, string> = {
  electricity: "Electricity",
  water: "Water",
  gas: "Gas",
  internet: "Internet",
  phone: "Phone",
  insurance: "Insurance",
  other: "Other",
};

export const BILLER_STATUS: Record<BillerStatus, Label> = {
  active: { label: "Trusted", tone: "success" },
  suspended: { label: "Paused", tone: "warning" },
};

export const BENEFICIARY_STATUS: Record<BeneficiaryStatus, Label> = {
  active: { label: "Approved", tone: "success" },
  revoked: { label: "Removed", tone: "muted" },
};

export const BILL_SOURCE: Record<BillSource, string> = {
  manual: "Added by hand",
  email_ingest: "From email",
  agent: "From agent",
  demo: "Demo",
};

export const INVALIDATION_REASON: Record<ApprovalInvalidationReason, string> = {
  bill_details_changed: "The bill details changed",
  beneficiary_revoked: "The payee was removed from the approved list",
  biller_suspended: "The biller was paused",
};

export const EXPECTED_OUTCOME: Record<WitnessExpectedOutcome, string> = {
  payment_present: "We expected: a payment",
  payment_absent: "We expected: no payment",
};

export const STEP_ACTOR: Record<StepActor, string> = {
  agent: "Agent",
  backend: "Keeper",
  armoriq: "Security guard",
  mock_bank: "Bank (simulated)",
  witness: "Witness",
  human: "Person",
};

export const STEP_RESULT: Record<StepResult, Label> = {
  ok: { label: "OK", tone: "success" },
  blocked: { label: "Blocked", tone: "danger" },
  pending: { label: "Waiting", tone: "warning" },
  info: { label: "Info", tone: "info" },
};

export const SECURITY_EVENT_TYPES: SecurityEventType[] = [
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
];

export function eventTypeLabel(t: SecurityEventType): string {
  const s = t.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatDate(d: string | null | undefined): string {
  if (!d) return "—";
  const date = /^\d{4}-\d{2}-\d{2}$/.test(d) ? new Date(`${d}T00:00:00`) : new Date(d);
  if (Number.isNaN(date.getTime())) return d;
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function formatDateTime(d: string | null | undefined): string {
  if (!d) return "—";
  const date = new Date(d);
  if (Number.isNaN(date.getTime())) return d;
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function relativeExpiry(expiresAt: string, now: number = Date.now()): string {
  const ms = new Date(expiresAt).getTime() - now;
  if (Number.isNaN(ms)) return "";
  if (ms <= 0) return "Expired";
  const mins = Math.round(ms / 60000);
  if (mins < 60) return `Expires in ${mins} minute${mins === 1 ? "" : "s"}`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `Expires in ${hours} hour${hours === 1 ? "" : "s"}`;
  const days = Math.round(hours / 24);
  return `Expires in ${days} days`;
}

export function friendlyMinutes(mins: number): string {
  if (!Number.isFinite(mins) || mins <= 0) return "";
  if (mins < 60) return `${mins} minutes`;
  if (mins < 1440) {
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h} hour${h === 1 ? "" : "s"}${m ? ` ${m} min` : ""}`;
  }
  const d = Math.floor(mins / 1440);
  const h = Math.floor((mins % 1440) / 60);
  return `${d} day${d === 1 ? "" : "s"}${h ? ` ${h} hour${h === 1 ? "" : "s"}` : ""}`;
}

export function lastFour(masked: string): string {
  return masked.slice(-4);
}
