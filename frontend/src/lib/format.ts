import type {
  ApprovalInvalidationReason,
  ApprovalStatus,
  AttemptStatus,
  BeneficiaryStatus,
  BillerCategory,
  BillerStatus,
  BillSource,
  BillStatus,
  Decision,
  MemberRole,
  ProcessingStatus,
  ReasonCode,
  SecurityEventType,
  Severity,
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
  awaiting_approval: { label: "Needs approval", tone: "warning" },
  processing: { label: "Processing", tone: "info" },
  needs_review: { label: "Needs review", tone: "warning" },
  paid: { label: "Paid", tone: "success" },
  blocked: { label: "Blocked", tone: "danger" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "muted" },
};

export const ATTEMPT_STATUS: Record<AttemptStatus, Label> = {
  succeeded: { label: "Bank processed it", tone: "success" },
  blocked: { label: "Blocked", tone: "danger" },
  requires_approval: { label: "Waiting for approval", tone: "warning" },
  executing: { label: "Executing", tone: "info" },
  failed: { label: "Failed", tone: "danger" },
};

export const DECISION: Record<Decision, Label> = {
  allow: { label: "Allowed", tone: "success" },
  deny: { label: "Denied", tone: "danger" },
  require_approval: { label: "Needs a person", tone: "warning" },
};

export const APPROVAL_STATUS: Record<ApprovalStatus, Label> = {
  pending: { label: "Pending", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
  expired: { label: "Expired", tone: "muted" },
  invalidated: { label: "Invalidated", tone: "danger" },
  consumed: { label: "Used", tone: "muted" },
};

export const WITNESS_VERDICT: Record<WitnessVerdict, Label> = {
  confirmed_paid: {
    label: "Witness confirms: payment found in bank ledger",
    tone: "success",
  },
  confirmed_no_payment: {
    label: "Witness confirms: no payment in bank ledger",
    tone: "info",
  },
  mismatch_detected: {
    label: "Witness warning: mismatch detected",
    tone: "danger",
  },
  unverifiable: {
    label: "Witness: unverifiable",
    tone: "warning",
  },
};

export const SEVERITY: Record<Severity, Label> = {
  info: { label: "Info", tone: "info" },
  warning: { label: "Warning", tone: "warning" },
  critical: { label: "Critical", tone: "danger" },
};

export const BILLER_STATUS: Record<BillerStatus, Label> = {
  active: { label: "Active", tone: "success" },
  suspended: { label: "Paused", tone: "warning" },
};

export const BENEFICIARY_STATUS: Record<BeneficiaryStatus, Label> = {
  active: { label: "Active", tone: "success" },
  revoked: { label: "Removed", tone: "muted" },
};

export const STEP_RESULT: Record<StepResult, Label> = {
  ok: { label: "OK", tone: "success" },
  blocked: { label: "Blocked", tone: "danger" },
  pending: { label: "Pending", tone: "warning" },
  info: { label: "Info", tone: "info" },
};

export const PROCESSING_STATUS: Record<ProcessingStatus, Label> = {
  idle: { label: "Idle", tone: "muted" },
  processing: { label: "Processing", tone: "info" },
  needs_review: { label: "Needs review", tone: "warning" },
  blocked: { label: "Blocked", tone: "danger" },
  paid: { label: "Paid", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "muted" },
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

export const REASON_CODE: Record<ReasonCode, string> = {
  within_limit: "Amount is within your safety limit",
  approval_valid: "Approved by a person",
  amount_exceeds_limit: "Amount exceeds automatic payment limit",
  beneficiary_not_approved: "Payee account is not on your approved list",
  biller_not_trusted: "Biller is not on your trusted list",
  biller_suspended: "Biller is currently paused",
  bill_not_payable: "Bill is not in a payable state",
  already_paid: "This bill has already been paid",
  currency_mismatch: "Currency mismatch",
  armoriq_denied: "Blocked by ArmorIQ security check",
  armoriq_hold: "Held by ArmorIQ security policy",
  armoriq_unavailable: "ArmorIQ security service unavailable",
  approval_expired: "Approval has expired",
  approval_details_changed: "Bill details changed after approval",
  bank_error: "Bank transfer failed",
};

export const BILL_SOURCE: Record<BillSource, string> = {
  manual: "Added manually",
  email_ingest: "From email",
  agent: "Found by agent",
  demo: "Demo bill",
};

export const EXPECTED_OUTCOME: Record<WitnessExpectedOutcome, string> = {
  payment_present: "Expected payment in bank ledger",
  payment_absent: "Expected no payment in bank ledger",
};

export const INVALIDATION_REASON: Record<ApprovalInvalidationReason, string> = {
  bill_details_changed: "Bill details changed",
  beneficiary_revoked: "Beneficiary was removed",
  biller_suspended: "Biller was paused",
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

export function eventTypeLabel(type: SecurityEventType): string {
  return type
    .split("_")
    .map((word, i) =>
      i === 0
        ? word.charAt(0).toUpperCase() + word.slice(1)
        : word.toLowerCase(),
    )
    .join(" ");
}

export function lastFour(val: string): string {
  if (!val) return "";
  return val.slice(-4);
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
    return new Intl.DateTimeFormat("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(d);
  } catch {
    return dateStr;
  }
}

export function formatDateTime(ts: string | null | undefined): string {
  if (!ts) return "—";
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return new Intl.DateTimeFormat("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }).format(d);
  } catch {
    return ts;
  }
}

export function relativeExpiry(ts: string): string {
  if (!ts) return "—";
  try {
    const expiryTime = new Date(ts).getTime();
    if (Number.isNaN(expiryTime)) return ts;
    const now = Date.now();
    const diffMs = expiryTime - now;
    const isPast = diffMs < 0;
    const absDiffSec = Math.floor(Math.abs(diffMs) / 1000);
    const minutes = Math.floor(absDiffSec / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
      return isPast
        ? `Expired ${days} day${days === 1 ? "" : "s"} ago`
        : `Expires in ${days} day${days === 1 ? "" : "s"}`;
    }
    if (hours > 0) {
      return isPast
        ? `Expired ${hours} hour${hours === 1 ? "" : "s"} ago`
        : `Expires in ${hours} hour${hours === 1 ? "" : "s"}`;
    }
    if (minutes > 0) {
      return isPast
        ? `Expired ${minutes} minute${minutes === 1 ? "" : "s"} ago`
        : `Expires in ${minutes} minute${minutes === 1 ? "" : "s"}`;
    }
    return isPast ? "Expired just now" : "Expires in a moment";
  } catch {
    return ts;
  }
}

export function friendlyMinutes(minutes: number): string {
  if (!minutes || minutes <= 0) return "0 minutes";
  if (minutes % 1440 === 0) {
    const days = minutes / 1440;
    return `${days} day${days === 1 ? "" : "s"}`;
  }
  if (minutes % 60 === 0) {
    const hours = minutes / 60;
    return `${hours} hour${hours === 1 ? "" : "s"}`;
  }
  if (minutes >= 60) {
    const hours = (minutes / 60).toFixed(1);
    return `${hours} hours`;
  }
  return `${minutes} minutes`;
}
