import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Eye } from "lucide-react";
import { WitnessReportCard } from "@/components/items";
import { EmptyState, FilterChips, ListBody, PageHeader, Pagination } from "@/components/common";
import { WITNESS_VERDICT } from "@/lib/format";
import { pageHead } from "@/lib/meta";
import { useWitnessReports } from "@/lib/queries";
import type { WitnessVerdict } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/witness")({
  head: () => pageHead("Witness checks", "Independent, read-only checks of the bank's own ledger."),
  component: WitnessPage,
});

function WitnessPage() {
  const [verdict, setVerdict] = useState<WitnessVerdict | undefined>();
  const [offset, setOffset] = useState(0);
  const q = useWitnessReports({ verdict, offset });
  return (
    <>
      <PageHeader title="What the Witness found" />
      <div className="mb-6 flex items-start gap-3 rounded-lg border border-info/30 bg-info-bg p-4 text-info">
        <Eye aria-hidden className="mt-1 size-6 shrink-0" />
        <p>
          The Witness is a separate, read-only checker. It never moves money and never trusts
          Keeper's own records — it looks at the bank's ledger itself.
        </p>
      </div>
      <FilterChips
        label="Filter by result"
        value={verdict}
        onChange={(v) => {
          setVerdict(v);
          setOffset(0);
        }}
        options={[
          { value: undefined, label: "All" },
          { value: "confirmed_paid", label: "Payment found" },
          { value: "confirmed_no_payment", label: "No payment" },
          { value: "mismatch_detected", label: "Mismatch" },
          { value: "unverifiable", label: "Could not check" },
        ]}
      />
      <span className="sr-only">{Object.values(WITNESS_VERDICT).length} possible results</span>
      <ListBody
        query={q}
        empty={<EmptyState text="Nothing here yet." />}
        render={(items) => (
          <ul className="space-y-3">
            {items.map((r) => (
              <WitnessReportCard key={r.id} report={r} />
            ))}
          </ul>
        )}
      />
      <Pagination offset={offset} total={q.data?.total ?? 0} onChange={setOffset} />
    </>
  );
}
