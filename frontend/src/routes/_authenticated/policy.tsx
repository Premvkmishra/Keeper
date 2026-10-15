import { useEffect, useState, type FormEvent } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ConfirmDialog,
  ErrorAlert,
  ErrorSummary,
  FieldError,
  ListSkeleton,
  PageHeader,
  Panel,
} from "@/components/common";
import { ApiError, friendlyErrorMessage } from "@/lib/api";
import { usePermissions } from "@/lib/auth";
import {
  BENEFICIARY_STATUS,
  BILLER_CATEGORY,
  BILLER_STATUS,
  formatDateTime,
  friendlyMinutes,
} from "@/lib/format";
import { formatMoney, normalizeMoney, validateMoney } from "@/lib/money";
import { pageHead } from "@/lib/meta";
import { useBeneficiaries, useBillers, usePolicy, useUpdatePolicy } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/policy")({
  head: () =>
    pageHead(
      "Safety limits",
      "Set how much Keeper may pay on its own and how long approvals last.",
    ),
  component: PolicyPage,
});

export function validateTtl(v: string): string | null {
  if (!/^\d+$/.test(v.trim())) return "Use a whole number of minutes.";
  const n = Number(v);
  if (n < 5 || n > 10080) return "Choose between 5 minutes and 10,080 minutes (7 days).";
  return null;
}

function PolicyPage() {
  const perms = usePermissions();
  const q = usePolicy();
  const billers = useBillers();
  const beneficiaries = useBeneficiaries();
  const update = useUpdatePolicy();
  const [limit, setLimit] = useState("");
  const [ttl, setTtl] = useState("");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [confirm, setConfirm] = useState(false);
  const [formErr, setFormErr] = useState<unknown>(null);

  useEffect(() => {
    if (q.data) {
      setLimit(q.data.auto_pay_limit);
      setTtl(String(q.data.approval_ttl_minutes));
    }
  }, [q.data]);

  if (q.isLoading) return <ListSkeleton rows={2} />;
  if (q.error || !q.data) return <ErrorAlert error={q.error} onRetry={() => q.refetch()} />;
  const p = q.data;
  const canEdit = perms.can_manage_policy;

  function submit(e: FormEvent) {
    e.preventDefault();
    const errs: Record<string, string> = {};
    const m = validateMoney(limit, { min: "0.00", max: "1000000.00" });
    if (m) errs.auto_pay_limit = m;
    const t = validateTtl(ttl);
    if (t) errs.approval_ttl_minutes = t;
    setErrors(errs);
    if (Object.keys(errs).length === 0) setConfirm(true);
  }

  async function save() {
    setFormErr(null);
    try {
      await update.mutateAsync({
        auto_pay_limit: normalizeMoney(limit) as string,
        approval_ttl_minutes: Number(ttl),
        expected_version: p.version,
      });
      toast.success("Safety limits saved.");
    } catch (err) {
      if (err instanceof ApiError && err.code === "version_conflict") {
        await q.refetch();
        setFormErr(
          new ApiError({
            ...err,
            code: err.code,
            message: "Someone else changed this. We've reloaded the latest values.",
            status: err.status,
            request_id: err.request_id,
            details: err.details,
          }),
        );
        toast.error("Someone else changed this. We've reloaded the latest values.");
      } else {
        if (err instanceof ApiError && err.code === "validation_error") setErrors(err.fieldErrors);
        setFormErr(err);
        toast.error(friendlyErrorMessage(err));
      }
    }
    setConfirm(false);
  }

  const normalized = normalizeMoney(limit);

  return (
    <>
      <PageHeader
        title="Your safety limits"
        intro="These rules decide what Keeper may pay on its own."
      />
      <Panel>
        <p className="text-lg">
          Keeper can pay up to{" "}
          <strong className="tabular">{formatMoney(p.auto_pay_limit, p.currency)}</strong> on its
          own. Anything above needs a person. An approval stays valid for{" "}
          <strong>{friendlyMinutes(p.approval_ttl_minutes)}</strong>.
        </p>
        <p className="mt-2 text-muted-foreground">
          Hard ceiling: {formatMoney(p.hard_payment_limit, p.currency)}. Human approval cannot
          override it.
        </p>
        <p className="mt-2 text-muted-foreground">
          Last changed {formatDateTime(p.updated_at)}
          {p.updated_by_name ? ` by ${p.updated_by_name}` : ""}.
        </p>
      </Panel>

      <Panel className="mt-6" title="Trusted billers">
        {billers.isLoading ? (
          <p className="text-muted-foreground">Loading trusted billers…</p>
        ) : billers.error ? (
          <ErrorAlert error={billers.error} onRetry={() => void billers.refetch()} />
        ) : (billers.data?.items.length ?? 0) === 0 ? (
          <p className="text-muted-foreground">No trusted billers are configured.</p>
        ) : (
          <ul className="divide-y">
            {billers.data?.items.map((biller) => (
              <li key={biller.id} className="flex flex-wrap justify-between gap-2 py-3">
                <span className="font-bold">{biller.name}</span>
                <span className="text-muted-foreground">
                  {BILLER_CATEGORY[biller.category]} · {BILLER_STATUS[biller.status].label} ·{" "}
                  {biller.active_beneficiary_count} approved payees
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel className="mt-6" title="Approved beneficiaries">
        {beneficiaries.isLoading ? (
          <p className="text-muted-foreground">Loading approved beneficiaries…</p>
        ) : beneficiaries.error ? (
          <ErrorAlert error={beneficiaries.error} onRetry={() => void beneficiaries.refetch()} />
        ) : (beneficiaries.data?.items.length ?? 0) === 0 ? (
          <p className="text-muted-foreground">No approved beneficiaries are configured.</p>
        ) : (
          <ul className="divide-y">
            {beneficiaries.data?.items.map((beneficiary) => (
              <li key={beneficiary.id} className="grid gap-1 py-3 sm:grid-cols-4 sm:gap-3">
                <span className="font-bold">{beneficiary.biller_name}</span>
                <span>{beneficiary.display_name}</span>
                <span className="tabular text-muted-foreground">
                  {beneficiary.account_number_masked} · {beneficiary.ifsc}
                </span>
                <span className="text-muted-foreground">
                  {BENEFICIARY_STATUS[beneficiary.status].label}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel className="mt-6" title="Security restrictions">
        <ul className="list-disc space-y-2 pl-5">
          <li>Only active trusted billers and approved beneficiary accounts can be paid.</li>
          <li>Payments above the household limit require an exact-detail human approval.</li>
          <li>The configured hard payment ceiling cannot be overridden by human approval.</li>
          <li>
            Agent payment tools require ArmorIQ proxy authorization; if unavailable, processing
            stops.
          </li>
        </ul>
      </Panel>

      <Panel className="mt-6" title={canEdit ? "Change limits" : "Limits"}>
        {!canEdit && (
          <p className="mb-4 text-muted-foreground">Only the owner can change these limits.</p>
        )}
        <form onSubmit={submit} noValidate className="max-w-md space-y-4" aria-live="polite">
          <ErrorSummary errors={errors} />
          {formErr ? <ErrorAlert error={formErr} /> : null}
          <div>
            <Label htmlFor="limit" className="text-base font-bold">
              Automatic payment limit (₹)
            </Label>
            <Input
              id="limit"
              inputMode="decimal"
              disabled={!canEdit}
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              onBlur={() => {
                const n = normalizeMoney(limit);
                if (n) setLimit(n);
              }}
              className="mt-1 h-12 text-base tabular"
              aria-describedby={`limit-hint${errors.auto_pay_limit ? " limit-error" : ""}`}
              aria-invalid={!!errors.auto_pay_limit}
            />
            <p id="limit-hint" className="mt-1 text-muted-foreground">
              Between ₹0.00 and ₹10,00,000.00.
            </p>
            <FieldError id="limit-error" msg={errors.auto_pay_limit} />
          </div>
          <div>
            <Label htmlFor="ttl" className="text-base font-bold">
              Approval valid for (minutes)
            </Label>
            <Input
              id="ttl"
              inputMode="numeric"
              disabled={!canEdit}
              value={ttl}
              onChange={(e) => setTtl(e.target.value)}
              className="mt-1 h-12 text-base tabular"
              aria-describedby={`ttl-hint${errors.approval_ttl_minutes ? " ttl-error" : ""}`}
              aria-invalid={!!errors.approval_ttl_minutes}
            />
            <p id="ttl-hint" className="mt-1 text-muted-foreground">
              {friendlyMinutes(Number(ttl)) ? `That is ${friendlyMinutes(Number(ttl))}. ` : ""}
              Between 5 minutes and 7 days.
            </p>
            <FieldError id="ttl-error" msg={errors.approval_ttl_minutes} />
          </div>
          {canEdit && (
            <Button type="submit" disabled={update.isPending}>
              Save limits
            </Button>
          )}
        </form>
      </Panel>

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Save these safety limits?"
        description={`Payments above ${normalized ? formatMoney(normalized) : limit} will always need a person's approval.`}
        confirmLabel="Save limits"
        pending={update.isPending}
        onConfirm={() => void save()}
      />
    </>
  );
}
