import { Link } from "@tanstack/react-router";
import {
  ApprovalStatusChip,
  AttemptStatusChip,
  BillStatusChip,
  DecisionChip,
  DemoTag,
  DestinationIndicator,
  SeverityChip,
  VerdictChip,
} from "@/components/status/StatusChip";
import { KV, TechDetails, useNow } from "@/components/common";
import { formatMoney } from "@/lib/money";
import {
  EXPECTED_OUTCOME,
  INVALIDATION_REASON,
  PROCESSING_STATUS,
  REASON_CODE,
  formatDate,
  formatDateTime,
  relativeExpiry,
} from "@/lib/format";
import type { Approval, Bill, PaymentAttempt, SecurityEvent, WitnessReport } from "@/lib/types";
import { cn } from "@/lib/utils";

export function BillCard({ bill }: { bill: Bill }) {
  return (
    <li className="rounded-lg border bg-card p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/bills/$billId"
              params={{ billId: bill.id }}
              className="text-lg font-bold text-primary underline-offset-4 hover:underline"
            >
              {bill.title}
            </Link>
            {bill.source === "demo" && <DemoTag />}
          </div>
          <p className="text-muted-foreground">
            {bill.biller_name ?? "No biller / unknown"} · Due {formatDate(bill.due_date)}
          </p>
        </div>
        <p className="money-lg">{formatMoney(bill.amount, bill.currency)}</p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <BillStatusChip status={bill.status} />
        <DestinationIndicator ok={bill.destination_matches_approved} />
      </div>
    </li>
  );
}

export function ApprovalCard({ approval }: { approval: Approval }) {
  const now = useNow();
  return (
    <li className="rounded-lg border bg-card p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="text-lg font-bold">{approval.bill_title}</p>
          <p className="text-muted-foreground">
            {approval.biller_name ?? "No biller"} · Payee{" "}
            {approval.destination_account_number_masked} · {approval.destination_ifsc}
          </p>
          {approval.status === "pending" && (
            <p className="mt-1">
              <strong>{relativeExpiry(approval.expires_at, now)}</strong>{" "}
              <span className="text-muted-foreground">({formatDateTime(approval.expires_at)})</span>
            </p>
          )}
          {approval.invalidated_reason && (
            <p className="mt-1 text-muted-foreground">
              {INVALIDATION_REASON[approval.invalidated_reason]}
            </p>
          )}
        </div>
        <p className="money-lg">{formatMoney(approval.amount, approval.currency)}</p>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <ApprovalStatusChip status={approval.status} />
        {approval.processing_status !== "idle" && (
          <span className="text-muted-foreground">
            {PROCESSING_STATUS[approval.processing_status].label}
          </span>
        )}
        <Link
          to="/approvals/$approvalId"
          params={{ approvalId: approval.id }}
          className="inline-flex min-h-12 items-center rounded-lg border bg-card px-5 font-bold text-primary hover:bg-accent"
        >
          Review
        </Link>
      </div>
    </li>
  );
}

export function EventItem({ event }: { event: SecurityEvent }) {
  return (
    <li
      className={cn(
        "rounded-lg border bg-card p-4",
        event.severity === "critical" && "border-l-4 border-l-danger",
      )}
    >
      <div className="flex flex-wrap items-center gap-3">
        <SeverityChip severity={event.severity} />
        <span className="text-muted-foreground">{formatDateTime(event.created_at)}</span>
      </div>
      <p className="mt-2">{event.message}</p>
      {event.bill_id && (
        <Link
          to="/bills/$billId"
          params={{ billId: event.bill_id }}
          className="mt-1 inline-block font-bold text-primary underline"
        >
          Open related bill
        </Link>
      )}
      <TechDetails>
        <dl className="mb-2">
          <KV k="event_type" v={event.event_type} />
          <KV k="actor_type" v={event.actor_type} />
          <KV k="event_id" v={event.id} />
          {event.attempt_id && <KV k="attempt_id" v={event.attempt_id} />}
        </dl>
        <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-card p-3 font-mono text-sm">
          {JSON.stringify(event.details, null, 2)}
        </pre>
      </TechDetails>
    </li>
  );
}

export function WitnessReportCard({ report }: { report: WitnessReport }) {
  return (
    <li className="rounded-lg border bg-card p-4">
      <div className="flex flex-wrap items-center gap-3">
        <VerdictChip verdict={report.verdict} />
      </div>
      <p className="mt-2 font-bold">{EXPECTED_OUTCOME[report.expected_outcome]}</p>
      <p>{report.summary}</p>
      <p className="tabular mt-1">
        Matching bank transactions: <strong>{report.ledger_match_count}</strong>
      </p>
      {report.matched_transactions.length === 0 ? (
        <p className="mt-2 text-muted-foreground">
          No matching transaction found in the bank ledger.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {report.matched_transactions.map((t) => (
            <li
              key={t.bank_txn_id}
              className="grid gap-1 rounded-md border bg-surface-alt p-3 sm:grid-cols-4"
            >
              <span>
                <span className="sr-only">Bank transaction </span>
                <span className="font-mono text-sm">{t.bank_txn_id}</span>
              </span>
              <span className="tabular font-bold">{formatMoney(t.amount, t.currency)}</span>
              <span>
                {t.destination_account_number_masked} · {t.destination_ifsc}
              </span>
              <span className="text-muted-foreground">{formatDateTime(t.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-muted-foreground">
        Checked {formatDateTime(report.checked_at)} · Looked from{" "}
        {formatDateTime(report.window_start)} to {formatDateTime(report.window_end)}
      </p>
      <p className="text-muted-foreground">Source: mock bank ledger (read-only)</p>
      <TechDetails>
        <dl>
          <KV k="report_id" v={report.id} />
          <KV k="attempt_id" v={report.attempt_id} />
          <KV k="bill_id" v={report.bill_id} />
          <KV k="ledger_source" v={report.ledger_source} />
          <KV k="read_only" v={String(report.read_only)} />
        </dl>
      </TechDetails>
    </li>
  );
}

export function AttemptSummary({ attempt }: { attempt: PaymentAttempt }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-bold">{attempt.bill_title}</p>
        <p className="money-lg">{formatMoney(attempt.amount, attempt.currency)}</p>
      </div>
      <p className="text-muted-foreground">
        Payee {attempt.destination_account_number_masked} · {attempt.destination_ifsc} · Started by{" "}
        {attempt.initiated_by_type === "agent" ? "the agent" : "a person"} ·{" "}
        {formatDateTime(attempt.created_at)}
      </p>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
            Authorization
          </p>
          <DecisionChip decision={attempt.decision} />
        </div>
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
            Payment execution
          </p>
          <AttemptStatusChip status={attempt.status} />
        </div>
      </div>
      <p>{REASON_CODE[attempt.reason_code]}</p>
    </div>
  );
}
