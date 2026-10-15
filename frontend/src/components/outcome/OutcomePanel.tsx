import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AttemptStatusChip, DecisionChip, VerdictChip } from "@/components/status/StatusChip";
import { KV, SubmitLabel, TechDetails } from "@/components/common";
import { REASON_CODE } from "@/lib/format";
import type { PaymentAttempt, PaymentOutcome, WitnessReport } from "@/lib/types";

export function Stage({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`stage-${n}-${title}`} className="rounded-lg border bg-card p-4">
      <h3 id={`stage-${n}-${title}`} className="mb-2 text-lg">
        {n}. {title}
      </h3>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

export function ExecutionText({ attempt }: { attempt: PaymentAttempt }) {
  return (
    <>
      <AttemptStatusChip status={attempt.status} />
      {attempt.status === "succeeded" && attempt.bank_reference && (
        <p>
          Bank reference: <span className="font-mono">{attempt.bank_reference}</span>
        </p>
      )}
      {attempt.status === "blocked" && <p>No payment was sent to the bank.</p>}
      {attempt.status === "requires_approval" && (
        <p>Waiting for a person to approve. Nothing has been sent to the bank.</p>
      )}
    </>
  );
}

export function WitnessText({
  report,
  onRecheck,
  recheckPending,
}: {
  report: WitnessReport | null | undefined;
  onRecheck?: () => void;
  recheckPending?: boolean;
}) {
  if (!report) {
    return (
      <>
        <p>Witness check not available yet.</p>
        {onRecheck && (
          <Button variant="outline" onClick={onRecheck} disabled={recheckPending}>
            <SubmitLabel
              pending={!!recheckPending}
              idle="Ask Witness to check again"
              busy="Checking…"
            />
          </Button>
        )}
      </>
    );
  }
  return (
    <>
      <VerdictChip verdict={report.verdict} />
      <p>{report.summary}</p>
      <p className="tabular">
        Matching bank transactions: <strong>{report.ledger_match_count}</strong>
      </p>
    </>
  );
}

export function OutcomePanel({
  outcome,
  onRecheck,
  recheckPending,
  showBillLink = true,
}: {
  outcome: PaymentOutcome;
  onRecheck?: () => void;
  recheckPending?: boolean;
  showBillLink?: boolean;
}) {
  const { attempt } = outcome;
  return (
    <div className="space-y-3" aria-live="polite">
      {outcome.idempotent_replay && (
        <p className="flex items-start gap-2 rounded-md border border-info/30 bg-info-bg p-3 text-info">
          <Info aria-hidden className="mt-1 size-5 shrink-0" />
          This request was already processed; showing the original result.
        </p>
      )}
      <Stage n={1} title="Authorization">
        <DecisionChip decision={outcome.decision} />
        <p className="font-bold">{REASON_CODE[outcome.reason_code]}</p>
        <p className="text-muted-foreground">{outcome.message}</p>
      </Stage>
      <Stage n={2} title="Payment execution">
        <ExecutionText attempt={attempt} />
      </Stage>
      <Stage n={3} title="Witness verification">
        <WitnessText
          report={outcome.witness_report}
          onRecheck={onRecheck}
          recheckPending={recheckPending}
        />
      </Stage>
      {showBillLink && (
        <p>
          <Link
            to="/bills/$billId"
            params={{ billId: outcome.bill.id }}
            className="font-bold text-primary underline"
          >
            Open this bill
          </Link>
        </p>
      )}
      <TechDetails>
        <dl>
          <KV k="reason_code" v={outcome.reason_code} />
          <KV k="attempt_id" v={attempt.id} />
          <KV k="bill_id" v={outcome.bill.id} />
          {outcome.approval && <KV k="approval_id" v={outcome.approval.id} />}
          {outcome.witness_report && <KV k="witness_report_id" v={outcome.witness_report.id} />}
        </dl>
      </TechDetails>
    </div>
  );
}
