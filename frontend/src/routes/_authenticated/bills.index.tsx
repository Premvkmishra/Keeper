import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BillCard } from "@/components/items";
import { BillFormDialog } from "@/components/BillForm";
import { EmptyState, FilterChips, ListBody, PageHeader, Pagination } from "@/components/common";
import { usePermissions } from "@/lib/auth";
import { BILL_STATUS } from "@/lib/format";
import { pageHead } from "@/lib/meta";
import { useBills } from "@/lib/queries";
import type { BillStatus } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/bills/")({
  head: () => pageHead("Bills", "All your household's bills and their payment status."),
  component: BillsPage,
});

function BillsPage() {
  const perms = usePermissions();
  const [status, setStatus] = useState<BillStatus | undefined>();
  const [offset, setOffset] = useState(0);
  const [adding, setAdding] = useState(false);
  const q = useBills({ status, offset });

  const addBtn = perms.can_manage_bills ? (
    <Button onClick={() => setAdding(true)}>
      <Plus aria-hidden /> Add a bill
    </Button>
  ) : undefined;

  return (
    <>
      <PageHeader title="Your bills" action={addBtn} />
      <FilterChips
        label="Filter by status"
        value={status}
        onChange={(v) => {
          setStatus(v);
          setOffset(0);
        }}
        options={[
          { value: undefined, label: "All" },
          ...(Object.keys(BILL_STATUS) as BillStatus[]).map((s) => ({
            value: s,
            label: BILL_STATUS[s].label,
          })),
        ]}
      />
      <ListBody
        query={q}
        empty={<EmptyState text="Nothing here yet." action={addBtn} />}
        render={(items) => (
          <ul className="space-y-3">
            {items.map((b) => (
              <BillCard key={b.id} bill={b} />
            ))}
          </ul>
        )}
      />
      <Pagination offset={offset} total={q.data?.total ?? 0} onChange={setOffset} />
      {adding && <BillFormDialog open={adding} onOpenChange={setAdding} />}
    </>
  );
}
