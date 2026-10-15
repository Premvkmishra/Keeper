import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { VerdictChip } from "@/components/status/StatusChip";
import { AttemptSummary, EventItem, WitnessReportCard } from "@/components/items";
import {
  EmptyState,
  ErrorAlert,
  FilterChips,
  KV,
  ListBody,
  ListSkeleton,
  PageHeader,
  Pagination,
  SubmitLabel,
  TechDetails,
} from "@/components/common";
import { ExecutionText } from "@/components/outcome/OutcomePanel";
import { friendlyErrorMessage } from "@/lib/api";
import { usePermissions } from "@/lib/auth";
import { ATTEMPT_STATUS } from "@/lib/format";
import { pageHead } from "@/lib/meta";
import { usePayment, usePayments, useWitnessReport, useWitnessVerify } from "@/lib/queries";
import type { AttemptStatus, PaymentAttempt } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/payments")({
  head: () =>
    pageHead(
      "Payments",
      "Every payment Keeper tried, with its authorization, execution and Witness result.",
    ),
  component: PaymentsPage,
});

function LazyVerdict({ attempt }: { attempt: PaymentAttempt }) {
  const [show, setShow] = useState(false);
  const r = useWitnessReport(attempt.latest_witness_report_id, show);
  if (!attempt.latest_witness_report_id)
    return <span className="text-muted-foreground">No Witness check yet</span>;
  if (!show)
    return (
      <Button variant="link" className="min-h-11 px-0" onClick={() => setShow(true)}>
        Show Witness result
      </Button>
    );
  if (r.isLoading) return <span>Loading Witness result…</span>;
  if (r.error) return <span className="text-danger">Couldn't load Witness result.</span>;
  return r.data ? <VerdictChip verdict={r.data.verdict} /> : null;
}

function PaymentsPage() {
  const [status, setStatus] = useState<AttemptStatus | undefined>();
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const q = usePayments({ status, offset });
  return (
    <>
      <PageHeader
        title="Payments Keeper tried"
        intro="Each payment shows three separate things: was it allowed, did the bank process it, and what the Witness found."
      />
      <FilterChips
        label="Filter by status"
        value={status}
        onChange={(v) => {
          setStatus(v);
          setOffset(0);
        }}
        options={[
          { value: undefined, label: "All" },
          ...(Object.keys(ATTEMPT_STATUS) as AttemptStatus[]).map((s) => ({
            value: s,
            label: ATTEMPT_STATUS[s].label,
          })),
        ]}
      />
      <ListBody
        query={q}
        empty={<EmptyState text="Nothing here yet." />}
        render={(items) => (
          <ul className="space-y-3">
            {items.map((a) => (
              <li key={a.id} className="rounded-lg border bg-card p-4">
                <AttemptSummary attempt={a} />
                <div className="mt-2">
                  <p className="text-sm font-bold uppercase tracking-wide text-muted-foreground">
                    Witness verification
                  </p>
                  <LazyVerdict attempt={a} />
                </div>
                <Button variant="outline" className="mt-3" onClick={() => setOpenId(a.id)}>
                  Open details
                </Button>
              </li>
            ))}
          </ul>
        )}
      />
      <Pagination offset={offset} total={q.data?.total ?? 0} onChange={setOffset} />
      <PaymentSheet id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}

function PaymentSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const perms = usePermissions();
  const q = usePayment(id);
  const verify = useWitnessVerify();
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent side="right" className="w-full overflow-y-auto bg-background sm:max-w-xl">
        <SheetHeader>
          <SheetTitle className="text-2xl">Payment details</SheetTitle>
          <SheetDescription className="text-base">
            Authorization, payment execution and Witness verification.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-5 px-4 pb-8">
          {q.isLoading ? (
            <ListSkeleton rows={3} />
          ) : q.error || !q.data ? (
            <ErrorAlert error={q.error} onRetry={() => q.refetch()} />
          ) : (
            <>
              <AttemptSummary attempt={q.data.attempt} />
              <ExecutionText attempt={q.data.attempt} />
              <Link
                to="/bills/$billId"
                params={{ billId: q.data.attempt.bill_id }}
                className="block font-bold text-primary underline"
              >
                Open the bill
              </Link>
              {perms.can_verify && (
                <Button
                  variant="outline"
                  disabled={verify.isPending}
                  onClick={() =>
                    verify.mutate(q.data.attempt.id, {
                      onSuccess: () => toast.success("The Witness checked the bank ledger again."),
                      onError: (e) => toast.error(friendlyErrorMessage(e)),
                    })
                  }
                >
                  <SubmitLabel
                    pending={verify.isPending}
                    idle="Ask Witness to check again"
                    busy="Checking…"
                  />
                </Button>
              )}
              <h3>Witness checks</h3>
              {q.data.witness_reports.length === 0 ? (
                <EmptyState text="Nothing here yet." />
              ) : (
                <ul className="space-y-3">
                  {q.data.witness_reports.map((r) => (
                    <WitnessReportCard key={r.id} report={r} />
                  ))}
                </ul>
              )}
              <h3>Security activity</h3>
              {q.data.events.length === 0 ? (
                <EmptyState text="Nothing here yet." />
              ) : (
                <ul className="space-y-3">
                  {q.data.events.map((e) => (
                    <EventItem key={e.id} event={e} />
                  ))}
                </ul>
              )}
              <TechDetails>
                <dl>
                  <KV k="attempt_id" v={q.data.attempt.id} />
                  <KV k="reason_code" v={q.data.attempt.reason_code} />
                  <KV k="approval_id" v={q.data.attempt.approval_id} />
                  <KV k="bank_reference" v={q.data.attempt.bank_reference} />
                </dl>
              </TechDetails>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
