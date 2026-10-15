import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  BillerStatusChip,
  BillStatusChip,
  DecisionChip,
  DemoTag,
  DestinationIndicator,
  ApprovalStatusChip,
} from "@/components/status/StatusChip";
import {
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  KV,
  ListSkeleton,
  Panel,
  TechDetails,
} from "@/components/common";
import { AttemptSummary, EventItem, WitnessReportCard } from "@/components/items";
import { ExecutionText, OutcomePanel, Stage, WitnessText } from "@/components/outcome/OutcomePanel";
import { BillFormDialog } from "@/components/BillForm";
import { friendlyErrorMessage } from "@/lib/api";
import { usePermissions } from "@/lib/auth";
import {
  BILL_SOURCE,
  BILLER_CATEGORY,
  REASON_CODE,
  formatDate,
  formatDateTime,
  lastFour,
} from "@/lib/format";
import { formatMoney } from "@/lib/money";
import { pageHead } from "@/lib/meta";
import { useBill, useCancelBill, usePayBill, useWitnessVerify } from "@/lib/queries";
import type { PaymentOutcome } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/bills/$billId")({
  head: () => pageHead("Bill details", "See a bill, its payee check and every payment step."),
  component: BillDetailPage,
});

function BillDetailPage() {
  const { billId } = Route.useParams();
  const perms = usePermissions();
  const q = useBill(billId);
  const pay = usePayBill(billId);
  const cancel = useCancelBill(billId);
  const verify = useWitnessVerify();
  const [payOpen, setPayOpen] = useState(false);
  const [payKey, setPayKey] = useState<string | null>(null);
  const [payError, setPayError] = useState<unknown>(null);
  const [outcome, setOutcome] = useState<PaymentOutcome | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);

  if (q.isLoading) return <ListSkeleton rows={4} />;
  if (q.error || !q.data) return <ErrorAlert error={q.error} onRetry={() => q.refetch()} />;
  const { bill, biller, approvals, attempts, witness_reports, events } = q.data;
  const latest = attempts[0];
  const latestWitness = latest
    ? witness_reports.find((r) => r.attempt_id === latest.id)
    : undefined;
  const canPay = perms.can_manage_bills && (bill.status === "received" || bill.status === "failed");
  const editable = perms.can_manage_bills && bill.status !== "paid" && bill.status !== "cancelled";
  const amount = formatMoney(bill.amount, bill.currency);
  const payee = biller?.name ?? bill.biller_name ?? "this payee";

  function openPay() {
    // Key is created when the dialog opens and reused on retry within the same dialog.
    setPayKey(crypto.randomUUID());
    setPayError(null);
    setPayOpen(true);
  }

  async function confirmPay() {
    if (!payKey || pay.isPending) return;
    setPayError(null);
    try {
      const res = await pay.mutateAsync({ idempotency_key: payKey });
      setOutcome(res);
      setPayOpen(false);
      if (res.decision === "allow" && res.attempt.status === "succeeded")
        toast.success("The bank processed the payment.");
      else if (res.decision === "require_approval")
        toast.info("This payment needs a person's approval.");
      else toast.warning(REASON_CODE[res.reason_code]);
    } catch (err) {
      setPayError(err);
      toast.error(friendlyErrorMessage(err));
    }
  }

  async function confirmCancel() {
    try {
      await cancel.mutateAsync();
      toast.success("Bill cancelled.");
      setCancelOpen(false);
    } catch (err) {
      toast.error(friendlyErrorMessage(err));
      setCancelOpen(false);
    }
  }

  async function recheck(attemptId: string) {
    try {
      await verify.mutateAsync({ attempt_id: attemptId });
      toast.success("The Witness checked the bank ledger again.");
    } catch (err) {
      toast.error(friendlyErrorMessage(err));
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/bills" className="font-bold text-primary underline">
        ← All bills
      </Link>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1>{bill.title}</h1>
            {bill.source === "demo" && <DemoTag />}
          </div>
          <p className="text-muted-foreground">
            {bill.biller_name ?? "No biller / unknown"} · {BILLER_CATEGORY[bill.category]} · Due{" "}
            {formatDate(bill.due_date)}
          </p>
        </div>
        <p className="text-3xl font-bold tabular">{amount}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <BillStatusChip status={bill.status} />
      </div>

      <div className="flex flex-wrap gap-3">
        {canPay && (
          <Button size="lg" onClick={openPay}>
            Pay this bill
          </Button>
        )}
        {editable && (
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            Edit
          </Button>
        )}
        {perms.can_manage_bills && bill.status !== "paid" && bill.status !== "cancelled" && (
          <Button variant="outline" onClick={() => setCancelOpen(true)}>
            Cancel bill
          </Button>
        )}
      </div>

      {outcome && (
        <Panel title="Result">
          <OutcomePanel
            outcome={outcome}
            showBillLink={false}
            onRecheck={perms.can_verify ? () => recheck(outcome.attempt.id) : undefined}
            recheckPending={verify.isPending}
          />
          {outcome.approval && outcome.decision === "require_approval" && (
            <Link
              to="/approvals/$approvalId"
              params={{ approvalId: outcome.approval.id }}
              className="mt-4 inline-flex min-h-12 items-center rounded-lg bg-primary px-5 font-bold text-primary-foreground hover:bg-primary-hover"
            >
              Review in Approval queue
            </Link>
          )}
        </Panel>
      )}

      <Panel title="Payee check">
        <dl className="space-y-1">
          <div>
            <dt className="inline font-bold">Account: </dt>
            <dd className="inline">{bill.destination_account_number_masked}</dd>
          </div>
          <div>
            <dt className="inline font-bold">IFSC: </dt>
            <dd className="inline">{bill.destination_ifsc}</dd>
          </div>
        </dl>
        <div className="mt-3 flex flex-wrap gap-2">
          <DestinationIndicator ok={bill.destination_matches_approved} />
          {biller ? (
            <BillerStatusChip status={biller.status} />
          ) : (
            <span className="text-muted-foreground">No biller linked</span>
          )}
        </div>
        {!bill.destination_matches_approved && (
          <p className="mt-3">
            This payee account is not on your approved list. Keeper will refuse to pay it.
          </p>
        )}
      </Panel>

      <Panel title="Latest payment, step by step">
        {latest ? (
          <div className="space-y-3">
            <Stage n={1} title="Authorization">
              <DecisionChip decision={latest.decision} />
              <p className="font-bold">{REASON_CODE[latest.reason_code]}</p>
              <p className="text-muted-foreground">{latest.message}</p>
            </Stage>
            <Stage n={2} title="Payment execution">
              <ExecutionText attempt={latest} />
            </Stage>
            <Stage n={3} title="Witness verification">
              <WitnessText
                report={latestWitness}
                onRecheck={perms.can_verify ? () => recheck(latest.id) : undefined}
                recheckPending={verify.isPending}
              />
            </Stage>
          </div>
        ) : (
          <EmptyState text="No payment has been tried for this bill yet." />
        )}
      </Panel>

      <Panel title="Payment attempts">
        {attempts.length === 0 ? (
          <EmptyState text="Nothing here yet." />
        ) : (
          <ul className="space-y-3">
            {attempts.map((a) => (
              <li key={a.id} className="rounded-lg border p-4">
                <AttemptSummary attempt={a} />
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Approvals">
        {approvals.length === 0 ? (
          <EmptyState text="Nothing here yet." />
        ) : (
          <ul className="space-y-3">
            {approvals.map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-4"
              >
                <div>
                  <ApprovalStatusChip status={a.status} />
                  <p className="mt-1 text-muted-foreground">
                    Requested {formatDateTime(a.requested_at)}
                  </p>
                </div>
                <Link
                  to="/approvals/$approvalId"
                  params={{ approvalId: a.id }}
                  className="font-bold text-primary underline"
                >
                  View approval
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Witness checks">
        {witness_reports.length === 0 ? (
          <EmptyState text="Nothing here yet." />
        ) : (
          <ul className="space-y-3">
            {witness_reports.map((r) => (
              <WitnessReportCard key={r.id} report={r} />
            ))}
          </ul>
        )}
      </Panel>

      <Panel title="Security activity">
        {events.length === 0 ? (
          <EmptyState text="Nothing here yet." />
        ) : (
          <ul className="space-y-3">
            {events.map((e) => (
              <EventItem key={e.id} event={e} />
            ))}
          </ul>
        )}
      </Panel>

      <TechDetails>
        <dl>
          <KV k="bill_id" v={bill.id} />
          <KV k="source" v={`${bill.source} (${BILL_SOURCE[bill.source]})`} />
          <KV k="invoice_ref" v={bill.invoice_ref} />
          <KV k="biller_id" v={bill.biller_id} />
          <KV k="created_at" v={bill.created_at} />
          <KV k="updated_at" v={bill.updated_at} />
          <KV k="paid_at" v={bill.paid_at} />
        </dl>
      </TechDetails>

      <ConfirmDialog
        open={payOpen}
        onOpenChange={(o) => {
          setPayOpen(o);
          if (!o) setPayError(null);
        }}
        title={`Pay ${amount} to ${payee}?`}
        description={`Payee account ••••${lastFour(bill.destination_account_number_masked)}, IFSC ${bill.destination_ifsc}. Keeper will check its safety rules before anything is sent.`}
        confirmLabel={payError ? "Try again" : `Pay ${amount}`}
        pending={pay.isPending}
        onConfirm={() => void confirmPay()}
      >
        {payError ? <ErrorAlert error={payError} /> : null}
      </ConfirmDialog>

      <ConfirmDialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title="Cancel this bill?"
        description="Keeper will not pay a cancelled bill. Any approval waiting for it stops."
        confirmLabel="Cancel bill"
        cancelLabel="Keep bill"
        destructive
        pending={cancel.isPending}
        onConfirm={() => void confirmCancel()}
      />

      {editOpen && <BillFormDialog open={editOpen} onOpenChange={setEditOpen} bill={bill} />}
    </div>
  );
}
