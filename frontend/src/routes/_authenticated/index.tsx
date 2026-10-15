import { createFileRoute, Link } from "@tanstack/react-router";
import { ApprovalCard, BillCard, EventItem, WitnessReportCard } from "@/components/items";
import { EmptyState, ErrorAlert, ListSkeleton, Panel } from "@/components/common";
import { formatMoney } from "@/lib/money";
import { pageHead } from "@/lib/meta";
import { useDashboard } from "@/lib/queries";
import type { Dashboard } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/")({
  head: () => pageHead("Home", "Your bills, approvals and safety checks at a glance."),
  component: HomePage,
});

export function summarySentence(d: Pick<Dashboard, "counts">): string {
  const ready = d.counts.bills_open;
  const waiting = d.counts.awaiting_approval;
  const a =
    ready === 0 ? "No bills are ready" : `${ready} bill${ready === 1 ? " is" : "s are"} ready`;
  const b =
    waiting === 0
      ? "nothing needs your approval"
      : `${waiting} need${waiting === 1 ? "s" : ""} your approval`;
  return `${a}, ${b}.`;
}

function HomePage() {
  const q = useDashboard();
  if (q.isLoading)
    return (
      <>
        <h1 className="mb-6">Home</h1>
        <ListSkeleton rows={5} />
      </>
    );
  if (q.error || !q.data)
    return (
      <>
        <h1 className="mb-6">Home</h1>
        <ErrorAlert error={q.error} onRetry={() => q.refetch()} />
      </>
    );
  const d = q.data;
  return (
    <div className="space-y-6">
      <div>
        <h1>{summarySentence(d)}</h1>
        <p className="mt-2 text-lg">
          Keeper can pay up to{" "}
          <strong className="tabular">
            {formatMoney(d.policy.auto_pay_limit, d.policy.currency)}
          </strong>{" "}
          on its own. Anything above needs you.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="Needs your approval"
          action={
            <Link to="/approvals" className="font-bold text-primary underline">
              See all
            </Link>
          }
        >
          {d.pending_approvals.length === 0 ? (
            <EmptyState text="Nothing is waiting for your approval." />
          ) : (
            <ul className="space-y-3">
              {d.pending_approvals.map((a) => (
                <ApprovalCard key={a.id} approval={a} />
              ))}
            </ul>
          )}
        </Panel>
        <Panel
          title="Upcoming bills"
          action={
            <Link to="/bills" className="font-bold text-primary underline">
              See all
            </Link>
          }
        >
          {d.upcoming_bills.length === 0 ? (
            <EmptyState text="No upcoming bills right now." />
          ) : (
            <ul className="space-y-3">
              {d.upcoming_bills.map((b) => (
                <BillCard key={b.id} bill={b} />
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel title="Safety at a glance">
        <dl className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-md bg-danger-bg p-4">
            <dt className="font-bold text-danger">Blocked in the last 30 days</dt>
            <dd className="money-lg text-danger">{d.counts.blocked_30d}</dd>
          </div>
          <div className="rounded-md bg-success-bg p-4">
            <dt className="font-bold text-success">Paid in the last 30 days</dt>
            <dd className="money-lg text-success">{d.counts.paid_30d_count}</dd>
          </div>
          <div className="rounded-md bg-surface-alt p-4">
            <dt className="font-bold">Total paid in the last 30 days</dt>
            <dd className="money-lg">{formatMoney(d.paid_30d_total, d.household.currency)}</dd>
          </div>
        </dl>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="Recent security activity"
          action={
            <Link to="/security" className="font-bold text-primary underline">
              See all
            </Link>
          }
        >
          {d.recent_security_events.length === 0 ? (
            <EmptyState text="Nothing here yet." />
          ) : (
            <ul className="space-y-3">
              {d.recent_security_events.map((e) => (
                <EventItem key={e.id} event={e} />
              ))}
            </ul>
          )}
        </Panel>
        <Panel
          title="Latest Witness checks"
          action={
            <Link to="/witness" className="font-bold text-primary underline">
              See all
            </Link>
          }
        >
          {d.latest_witness_reports.length === 0 ? (
            <EmptyState text="Nothing here yet." />
          ) : (
            <ul className="space-y-3">
              {d.latest_witness_reports.map((r) => (
                <WitnessReportCard key={r.id} report={r} />
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  );
}
