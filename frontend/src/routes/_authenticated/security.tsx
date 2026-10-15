import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Label } from "@/components/ui/label";
import { EventItem } from "@/components/items";
import { EmptyState, FilterChips, ListBody, PageHeader, Pagination } from "@/components/common";
import { SECURITY_EVENT_TYPES, SEVERITY, eventTypeLabel } from "@/lib/format";
import { pageHead } from "@/lib/meta";
import { useSecurityEvents } from "@/lib/queries";
import type { SecurityEventType, Severity } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/security")({
  head: () =>
    pageHead("Security activity", "Everything Keeper allowed, blocked or flagged, newest first."),
  component: SecurityPage,
});

function SecurityPage() {
  const [severity, setSeverity] = useState<Severity | undefined>();
  const [eventType, setEventType] = useState<SecurityEventType | undefined>();
  const [offset, setOffset] = useState(0);
  const q = useSecurityEvents({ severity, event_type: eventType, offset });
  return (
    <>
      <PageHeader title="What Keeper has been watching" />
      <FilterChips
        label="Filter by severity"
        value={severity}
        onChange={(v) => {
          setSeverity(v);
          setOffset(0);
        }}
        options={[
          { value: undefined, label: "All" },
          ...(Object.keys(SEVERITY) as Severity[]).map((s) => ({
            value: s,
            label: SEVERITY[s].label,
          })),
        ]}
      />
      <div className="mb-5 max-w-sm">
        <Label htmlFor="event-type" className="text-base font-bold">
          Type of activity
        </Label>
        <select
          id="event-type"
          className="mt-1 h-12 w-full rounded-md border border-input bg-card px-3 text-base"
          value={eventType ?? ""}
          onChange={(e) => {
            setEventType((e.target.value || undefined) as SecurityEventType | undefined);
            setOffset(0);
          }}
        >
          <option value="">All types</option>
          {SECURITY_EVENT_TYPES.map((t) => (
            <option key={t} value={t}>
              {eventTypeLabel(t)}
            </option>
          ))}
        </select>
      </div>
      <ListBody
        query={q}
        empty={<EmptyState text="Nothing here yet." />}
        render={(items) => (
          <ul className="space-y-3">
            {items.map((e) => (
              <EventItem key={e.id} event={e} />
            ))}
          </ul>
        )}
      />
      <Pagination offset={offset} total={q.data?.total ?? 0} onChange={setOffset} />
    </>
  );
}
