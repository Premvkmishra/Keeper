import {
  AlertTriangle,
  CheckCircle2,
  Info,
  MinusCircle,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import type { Label, Tone } from "@/lib/format";
import {
  APPROVAL_STATUS,
  ATTEMPT_STATUS,
  BENEFICIARY_STATUS,
  BILL_STATUS,
  BILLER_STATUS,
  DECISION,
  SEVERITY,
  STEP_RESULT,
  WITNESS_VERDICT,
} from "@/lib/format";
import type {
  ApprovalStatus,
  AttemptStatus,
  BeneficiaryStatus,
  BillerStatus,
  BillStatus,
  Decision,
  Severity,
  StepResult,
  WitnessVerdict,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const TONE_CLASS: Record<Tone, string> = {
  info: "bg-info-bg text-info border-info/30",
  warning: "bg-warning-bg text-warning border-warning/30",
  success: "bg-success-bg text-success border-success/30",
  danger: "bg-danger-bg text-danger border-danger/30",
  muted: "bg-muted text-muted-foreground border-border",
};

const TONE_ICON: Record<Tone, LucideIcon> = {
  info: Info,
  warning: AlertTriangle,
  success: CheckCircle2,
  danger: XCircle,
  muted: MinusCircle,
};

export function toneClass(t: Tone) {
  return TONE_CLASS[t];
}

export function Chip({ label, tone, className }: Label & { className?: string }) {
  const Icon = TONE_ICON[tone];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-base font-bold leading-tight",
        TONE_CLASS[tone],
        className,
      )}
    >
      <Icon aria-hidden className="size-4 shrink-0" />
      <span>{label}</span>
    </span>
  );
}

export const BillStatusChip = ({ status }: { status: BillStatus }) => (
  <Chip {...BILL_STATUS[status]} />
);
export const AttemptStatusChip = ({ status }: { status: AttemptStatus }) => (
  <Chip {...ATTEMPT_STATUS[status]} />
);
export const DecisionChip = ({ decision }: { decision: Decision }) => (
  <Chip {...DECISION[decision]} />
);
export const ApprovalStatusChip = ({ status }: { status: ApprovalStatus }) => (
  <Chip {...APPROVAL_STATUS[status]} />
);
export const VerdictChip = ({ verdict }: { verdict: WitnessVerdict }) => (
  <Chip {...WITNESS_VERDICT[verdict]} />
);
export const SeverityChip = ({ severity }: { severity: Severity }) => (
  <Chip {...SEVERITY[severity]} />
);
export const BillerStatusChip = ({ status }: { status: BillerStatus }) => (
  <Chip {...BILLER_STATUS[status]} />
);
export const BeneficiaryStatusChip = ({ status }: { status: BeneficiaryStatus }) => (
  <Chip {...BENEFICIARY_STATUS[status]} />
);
export const StepResultChip = ({ result }: { result: StepResult }) => (
  <Chip {...STEP_RESULT[result]} />
);

export function DestinationIndicator({ ok }: { ok: boolean }) {
  return ok ? (
    <Chip label="Approved payee" tone="success" />
  ) : (
    <Chip label="Unapproved payee" tone="warning" />
  );
}

export function DemoTag() {
  return <Chip label="Demo" tone="muted" className="px-2 py-0.5 text-sm" />;
}
