import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ApprovalCard } from "@/components/items";
import { EmptyState, FilterChips, ListBody, PageHeader, Pagination } from "@/components/common";
import { APPROVAL_STATUS } from "@/lib/format";
import { pageHead } from "@/lib/meta";
import { useApprovals } from "@/lib/queries";
import type { ApprovalStatus } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/approvals/")({
  head: () => pageHead("Approvals", "Payments waiting for a person to check and approve."),
  component: ApprovalsPage,
});

function ApprovalsPage() {
  const [status, setStatus] = useState<ApprovalStatus | undefined>("pending");
  const [offset, setOffset] = useState(0);
  const q = useApprovals({ status, offset });
  return (
    <>
      <PageHeader
        title="Payments waiting for you"
        intro="These payments are above your automatic limit, so a person must check them."
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
          ...(Object.keys(APPROVAL_STATUS) as ApprovalStatus[]).map((s) => ({
            value: s,
            label: APPROVAL_STATUS[s].label,
          })),
        ]}
      />
      <ListBody
        query={q}
        empty={
          <EmptyState
            text={
              status === "pending" ? "Nothing is waiting for your approval." : "Nothing here yet."
            }
          />
        }
        render={(items) => (
          <ul className="space-y-3">
            {items.map((a) => (
              <ApprovalCard key={a.id} approval={a} />
            ))}
          </ul>
        )}
      />
      <Pagination offset={offset} total={q.data?.total ?? 0} onChange={setOffset} />
    </>
  );
}
