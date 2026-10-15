import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApprovalStatusChip, BillStatusChip } from "@/components/status/StatusChip";
import {
  ConfirmDialog,
  ErrorAlert,
  KV,
  ListSkeleton,
  Panel,
  TechDetails,
  useNow,
} from "@/components/common";
import { ApproveDialog } from "@/components/ApproveDialog";
import { friendlyErrorMessage } from "@/lib/api";
import { usePermissions } from "@/lib/auth";
import {
  INVALIDATION_REASON,
  PROCESSING_STATUS,
  REASON_CODE,
  formatDateTime,
  relativeExpiry,
} from "@/lib/format";
import { formatMoney } from "@/lib/money";
import { pageHead } from "@/lib/meta";
import {
  useApproval,
  useApproveApproval,
  useDashboard,
  useRejectApproval,
  useRetryApproval,
} from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/approvals/$approvalId")({
  head: () =>
    pageHead("Review approval", "Check the exact amount and payee before approving a payment."),
  component: ApprovalDetailPage,
});

function ApprovalDetailPage() {
  const { approvalId } = Route.useParams();
  const perms = usePermissions();
  const q = useApproval(approvalId);
  const dash = useDashboard();
  const approve = useApproveApproval(approvalId);
  const reject = useRejectApproval(approvalId);
  const retry = useRetryApproval(approvalId);
  const now = useNow();
  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectNote, setRejectNote] = useState("");
  const [actionError, setActionError] = useState<unknown>(null);

  if (q.isLoading) return <ListSkeleton rows={3} />;
  if (q.error || !q.data) return <ErrorAlert error={q.error} onRetry={() => q.refetch()} />;
  const { approval, bill, biller } = q.data;
  const amount = formatMoney(approval.amount, approval.currency);
  const canAct = perms.can_approve && approval.status === "pending";
  const limit = dash.data
    ? formatMoney(dash.data.policy.auto_pay_limit, dash.data.policy.currency)
    : null;

  async function doApprove(note?: string) {
    setActionError(null);
    try {
      const result = await approve.mutateAsync({
        details_hash: approval.details_hash,
        ...(note ? { note } : {}),
      });
      setApproveOpen(false);
      await q.refetch();
      if (result.processing_status === "needs_review") {
        toast.warning(result.processing_message ?? "Approval recorded; processing needs review.");
      } else {
        toast.info("Approval recorded. Payment processing has started.");
      }
    } catch (err) {
      setApproveOpen(false);
      setActionError(err);
      toast.error(friendlyErrorMessage(err));
      void q.refetch();
    }
  }

  async function doReject() {
    setActionError(null);
    try {
      await reject.mutateAsync(rejectNote.trim() ? { note: rejectNote.trim() } : {});
      setRejectOpen(false);
      toast.success("Declined. Nothing was paid.");
    } catch (err) {
      setRejectOpen(false);
      setActionError(err);
      toast.error(friendlyErrorMessage(err));
    }
  }

  async function doRetry() {
    setActionError(null);
    try {
      const result = await retry.mutateAsync();
      await q.refetch();
      if (result.processing_status === "processing") {
        toast.info("Processing resumed. The status will update here.");
      } else {
        toast.warning(result.processing_message ?? "Processing still needs review.");
      }
    } catch (err) {
      setActionError(err);
      toast.error(friendlyErrorMessage(err));
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/approvals" className="font-bold text-primary underline">
        ← Approval queue
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h1>Please check this payment</h1>
        <ApprovalStatusChip status={approval.status} />
      </div>

      <section
        aria-label="Details being approved"
        className="rounded-lg border-2 border-primary bg-card p-6"
      >
        <dl className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <dt className="font-bold text-muted-foreground">Amount</dt>
            <dd className="text-4xl font-bold tabular">{amount}</dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Biller</dt>
            <dd className="text-lg">
              {approval.biller_name ?? biller?.name ?? "No biller / unknown"}
            </dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Bill</dt>
            <dd className="text-lg">{approval.bill_title}</dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Payee account</dt>
            <dd className="text-lg tabular">{approval.destination_account_number_masked}</dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Payee IFSC</dt>
            <dd className="text-lg">{approval.destination_ifsc}</dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Requested by</dt>
            <dd className="text-lg">
              {approval.requested_by_type === "agent" ? "Keeper's agent" : "A person"}
            </dd>
          </div>
          <div>
            <dt className="font-bold text-muted-foreground">Expires</dt>
            <dd className="text-lg">
              {formatDateTime(approval.expires_at)}
              {approval.status === "pending" && (
                <span className="block font-bold">{relativeExpiry(approval.expires_at, now)}</span>
              )}
            </dd>
          </div>
        </dl>
        <p className="mt-5 rounded-md bg-warning-bg p-3 text-warning">
          <strong>Why approval is needed:</strong> {REASON_CODE[approval.reason_code]}
          {limit ? ` of ${limit}` : ""}.
        </p>
      </section>

      {approval.invalidated_reason && (
        <p
          role="status"
          className="rounded-md border border-warning/40 bg-warning-bg p-4 text-warning"
        >
          This approval was cancelled: {INVALIDATION_REASON[approval.invalidated_reason]}. Nothing
          was paid.
        </p>
      )}
      {approval.decided_at && (
        <p className="text-muted-foreground">
          Decided {formatDateTime(approval.decided_at)}
          {approval.decided_by_name ? ` by ${approval.decided_by_name}` : ""}
          {approval.decision_note ? ` — "${approval.decision_note}"` : ""}
        </p>
      )}

      {actionError ? <ErrorAlert error={actionError} /> : null}

      {canAct && (
        <div className="flex flex-wrap gap-3">
          <Button size="lg" onClick={() => setApproveOpen(true)}>
            Approve and pay {amount}
          </Button>
          <Button size="lg" variant="outline" onClick={() => setRejectOpen(true)}>
            Decline
          </Button>
        </div>
      )}
      {!perms.can_approve && approval.status === "pending" && (
        <p className="text-muted-foreground">
          You can view this approval, but you can't approve or decline it.
        </p>
      )}

      {approval.processing_status !== "idle" && (
        <Panel title="Payment processing">
          <p className="font-bold">{PROCESSING_STATUS[approval.processing_status].label}</p>
          <p className="mt-1 text-muted-foreground">{approval.processing_message}</p>
          {approval.processing_status === "needs_review" && perms.can_approve && (
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => void doRetry()}
              disabled={retry.isPending}
            >
              Retry processing
            </Button>
          )}
        </Panel>
      )}

      <Panel title="The bill">
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to="/bills/$billId"
            params={{ billId: bill.id }}
            className="font-bold text-primary underline"
          >
            {bill.title}
          </Link>
          <BillStatusChip status={bill.status} />
        </div>
      </Panel>

      <TechDetails>
        <dl>
          <KV k="approval_id" v={approval.id} />
          <KV k="bill_id" v={approval.bill_id} />
          <KV k="reason_code" v={approval.reason_code} />
          <KV k="details_hash" v={approval.details_hash} />
          <KV k="requested_at" v={approval.requested_at} />
        </dl>
      </TechDetails>

      <ApproveDialog
        approval={approval}
        open={approveOpen}
        onOpenChange={setApproveOpen}
        pending={approve.isPending}
        onConfirm={(note) => void doApprove(note)}
      />
      <ConfirmDialog
        open={rejectOpen}
        onOpenChange={setRejectOpen}
        title="Decline this payment?"
        description="Nothing will be paid. The bill goes back to your list."
        confirmLabel="Decline"
        destructive
        pending={reject.isPending}
        onConfirm={() => void doReject()}
      >
        <div>
          <Label htmlFor="reject-note" className="text-base font-bold">
            Note (optional)
          </Label>
          <Textarea
            id="reject-note"
            maxLength={500}
            value={rejectNote}
            onChange={(e) => setRejectNote(e.target.value)}
            className="mt-1 text-base"
          />
        </div>
      </ConfirmDialog>
    </div>
  );
}
