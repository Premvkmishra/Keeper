import { useState, type FormEvent } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { Plus, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { BeneficiaryStatusChip, BillerStatusChip } from "@/components/status/StatusChip";
import {
  ConfirmDialog,
  EmptyState,
  ErrorAlert,
  ErrorSummary,
  FieldError,
  ListSkeleton,
  PageHeader,
  SubmitLabel,
} from "@/components/common";
import { ACCOUNT_RE, IFSC_RE } from "@/components/BillForm";
import { ApiError, friendlyErrorMessage } from "@/lib/api";
import { usePermissions } from "@/lib/auth";
import { BILLER_CATEGORY } from "@/lib/format";
import { pageHead } from "@/lib/meta";
import {
  useBeneficiaries,
  useBillers,
  useCreateBeneficiary,
  useCreateBiller,
  useReactivateBiller,
  useRevokeBeneficiary,
  useSuspendBiller,
  useUpdateBiller,
} from "@/lib/queries";
import type { Beneficiary, Biller, BillerCategory } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/billers")({
  head: () =>
    pageHead("Trusted billers", "The only billers and payee accounts Keeper is allowed to pay."),
  component: BillersPage,
});

const selectClass = "mt-1 h-12 w-full rounded-md border border-input bg-card px-3 text-base";

function BillersPage() {
  const perms = usePermissions();
  const billers = useBillers();
  const bens = useBeneficiaries();
  const suspend = useSuspendBiller();
  const reactivate = useReactivateBiller();
  const revoke = useRevokeBeneficiary();
  const [billerForm, setBillerForm] = useState<{ open: boolean; biller?: Biller }>({ open: false });
  const [payeeFor, setPayeeFor] = useState<Biller | null>(null);
  const [toggle, setToggle] = useState<Biller | null>(null);
  const [removing, setRemoving] = useState<Beneficiary | null>(null);

  const owner = perms.can_manage_billers;

  async function doToggle() {
    if (!toggle) return;
    try {
      if (toggle.status === "active") await suspend.mutateAsync(toggle.id);
      else await reactivate.mutateAsync(toggle.id);
      toast.success(
        toggle.status === "active"
          ? `${toggle.name} is paused.`
          : `${toggle.name} is trusted again.`,
      );
    } catch (e) {
      toast.error(friendlyErrorMessage(e));
    }
    setToggle(null);
  }

  async function doRevoke() {
    if (!removing) return;
    try {
      await revoke.mutateAsync(removing.id);
      toast.success("Payee removed. Keeper will refuse payments to this account.");
    } catch (e) {
      toast.error(friendlyErrorMessage(e));
    }
    setRemoving(null);
  }

  return (
    <>
      <PageHeader
        title="Billers Keeper trusts"
        action={
          owner ? (
            <Button onClick={() => setBillerForm({ open: true })}>
              <Plus aria-hidden /> Add biller
            </Button>
          ) : undefined
        }
      />
      <div className="mb-6 flex items-start gap-3 rounded-lg border border-info/30 bg-info-bg p-4 text-info">
        <ShieldCheck aria-hidden className="mt-1 size-6 shrink-0" />
        <p>
          Keeper only pays accounts listed here. Only the owner can change this list — the AI agent
          never can.
          {!owner && (
            <strong className="block">
              You can view this list, but only the owner can change it.
            </strong>
          )}
        </p>
      </div>

      {billers.isLoading || bens.isLoading ? (
        <ListSkeleton />
      ) : billers.error ? (
        <ErrorAlert error={billers.error} onRetry={() => billers.refetch()} />
      ) : (billers.data?.items.length ?? 0) === 0 ? (
        <EmptyState
          text="No trusted billers yet."
          action={
            owner ? (
              <Button onClick={() => setBillerForm({ open: true })}>Add biller</Button>
            ) : undefined
          }
        />
      ) : (
        <ul className="space-y-4">
          {billers.data?.items.map((b) => {
            const payees = (bens.data?.items ?? []).filter((p) => p.biller_id === b.id);
            return (
              <li key={b.id} className="rounded-lg border bg-card p-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="text-xl">{b.name}</h2>
                    <p className="text-muted-foreground">
                      {BILLER_CATEGORY[b.category]}
                      {b.consumer_reference ? ` · Customer no. ${b.consumer_reference}` : ""}
                    </p>
                  </div>
                  <BillerStatusChip status={b.status} />
                </div>
                {bens.error ? (
                  <ErrorAlert error={bens.error} onRetry={() => bens.refetch()} />
                ) : (
                  <>
                    <h3 className="mt-4 text-lg">Approved payees</h3>
                    {payees.length === 0 ? (
                      <p className="text-muted-foreground">No approved payee accounts yet.</p>
                    ) : (
                      <ul className="mt-2 space-y-2">
                        {payees.map((p) => (
                          <li
                            key={p.id}
                            className="flex flex-col gap-2 rounded-md border bg-surface-alt p-3 sm:flex-row sm:items-center sm:justify-between"
                          >
                            <div>
                              <p className="font-bold">{p.display_name}</p>
                              <p className="tabular">
                                {p.account_number_masked} · {p.ifsc}
                              </p>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <BeneficiaryStatusChip status={p.status} />
                              {owner && p.status === "active" && (
                                <Button variant="outline" size="sm" onClick={() => setRemoving(p)}>
                                  Remove payee
                                </Button>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </>
                )}
                {owner && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button variant="outline" size="sm" onClick={() => setPayeeFor(b)}>
                      <Plus aria-hidden /> Add approved payee
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setBillerForm({ open: true, biller: b })}
                    >
                      Edit
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setToggle(b)}>
                      {b.status === "active" ? "Pause" : "Resume"}
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {billerForm.open && (
        <BillerDialog biller={billerForm.biller} onClose={() => setBillerForm({ open: false })} />
      )}
      {payeeFor && <PayeeDialog biller={payeeFor} onClose={() => setPayeeFor(null)} />}
      <ConfirmDialog
        open={!!toggle}
        onOpenChange={(o) => !o && setToggle(null)}
        title={toggle?.status === "active" ? `Pause ${toggle?.name}?` : `Resume ${toggle?.name}?`}
        description={
          toggle?.status === "active"
            ? "Keeper will refuse to pay this biller while it is paused. Any approvals waiting for its bills will be cancelled."
            : "Keeper will be allowed to pay this biller again, to its approved payees only."
        }
        confirmLabel={toggle?.status === "active" ? "Pause biller" : "Resume biller"}
        destructive={toggle?.status === "active"}
        pending={suspend.isPending || reactivate.isPending}
        onConfirm={() => void doToggle()}
      />
      <ConfirmDialog
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title="Remove this payee?"
        description={`Keeper will refuse payments to this account (${removing?.account_number_masked ?? ""}, ${removing?.ifsc ?? ""}).`}
        confirmLabel="Remove payee"
        destructive
        pending={revoke.isPending}
        onConfirm={() => void doRevoke()}
      />
    </>
  );
}

function BillerDialog({ biller, onClose }: { biller?: Biller; onClose: () => void }) {
  const create = useCreateBiller();
  const update = useUpdateBiller();
  const [name, setName] = useState(biller?.name ?? "");
  const [category, setCategory] = useState<BillerCategory>(biller?.category ?? "electricity");
  const [ref, setRef] = useState(biller?.consumer_reference ?? "");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [formErr, setFormErr] = useState<unknown>(null);
  const pending = create.isPending || update.isPending;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = "Please enter the biller's name.";
    else if (name.length > 120) errs.name = "The name can be at most 120 characters.";
    if (ref.length > 64)
      errs.consumer_reference = "The customer number can be at most 64 characters.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setFormErr(null);
    try {
      const body = {
        name: name.trim(),
        category,
        ...(ref.trim() ? { consumer_reference: ref.trim() } : {}),
      };
      if (biller) await update.mutateAsync({ id: biller.id, body });
      else await create.mutateAsync(body);
      toast.success(biller ? "Biller updated." : "Biller added.");
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.code === "validation_error") setErrors(err.fieldErrors || {});
      setFormErr(err);
      toast.error(friendlyErrorMessage(err));
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl">{biller ? "Edit biller" : "Add biller"}</DialogTitle>
          <DialogDescription className="text-base text-muted-foreground">
            Billers you add here become trusted.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="space-y-4" aria-live="polite">
          <ErrorSummary errors={errors} />
          {formErr && !(formErr instanceof ApiError && formErr.code === "validation_error") ? (
            <ErrorAlert error={formErr} />
          ) : null}
          <div>
            <Label htmlFor="b-name" className="text-base font-bold">
              Name
            </Label>
            <Input
              id="b-name"
              value={name}
              maxLength={120}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 h-12 text-base"
              aria-describedby={errors.name ? "b-name-error" : undefined}
              aria-invalid={!!errors.name}
            />
            <FieldError id="b-name-error" msg={errors.name} />
          </div>
          <div>
            <Label htmlFor="b-cat" className="text-base font-bold">
              Category
            </Label>
            <select
              id="b-cat"
              className={selectClass}
              value={category}
              onChange={(e) => setCategory(e.target.value as BillerCategory)}
            >
              {(Object.keys(BILLER_CATEGORY) as BillerCategory[]).map((c) => (
                <option key={c} value={c}>
                  {BILLER_CATEGORY[c]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="b-ref" className="text-base font-bold">
              Customer number (optional)
            </Label>
            <Input
              id="b-ref"
              value={ref}
              maxLength={64}
              onChange={(e) => setRef(e.target.value)}
              className="mt-1 h-12 text-base"
              aria-describedby={errors.consumer_reference ? "b-ref-error" : undefined}
            />
            <FieldError id="b-ref-error" msg={errors.consumer_reference} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              <SubmitLabel pending={pending} idle={biller ? "Save changes" : "Add biller"} />
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PayeeDialog({ biller, onClose }: { biller: Biller; onClose: () => void }) {
  const create = useCreateBeneficiary();
  const [displayName, setDisplayName] = useState("");
  const [account, setAccount] = useState("");
  const [ifsc, setIfsc] = useState("");
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [formErr, setFormErr] = useState<unknown>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (create.isPending) return;
    const errs: Record<string, string> = {};
    if (!displayName.trim()) errs.display_name = "Please enter a name for this payee.";
    else if (displayName.length > 120)
      errs.display_name = "The name can be at most 120 characters.";
    if (!ACCOUNT_RE.test(account))
      errs.account_number = "Enter the full account number: 9 to 18 digits.";
    if (!IFSC_RE.test(ifsc)) errs.ifsc = "IFSC looks like ABCD0123456 (11 characters).";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setFormErr(null);
    try {
      await create.mutateAsync({
        biller_id: biller.id,
        display_name: displayName.trim(),
        account_number: account,
        ifsc,
      });
      toast.success("Approved payee added.");
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.code === "validation_error") setErrors(err.fieldErrors || {});
      setFormErr(err);
      toast.error(friendlyErrorMessage(err));
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl">Add approved payee for {biller.name}</DialogTitle>
          <DialogDescription className="text-base text-muted-foreground">
            Keeper will only pay this biller to accounts you add here.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="space-y-4" aria-live="polite">
          <ErrorSummary errors={errors} />
          {formErr && !(formErr instanceof ApiError && formErr.code === "validation_error") ? (
            <ErrorAlert error={formErr} />
          ) : null}
          <div>
            <Label htmlFor="p-name" className="text-base font-bold">
              Payee name
            </Label>
            <Input
              id="p-name"
              value={displayName}
              maxLength={120}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1 h-12 text-base"
              aria-describedby={errors.display_name ? "p-name-error" : undefined}
              aria-invalid={!!errors.display_name}
            />
            <FieldError id="p-name-error" msg={errors.display_name} />
          </div>
          <div>
            <Label htmlFor="p-acct" className="text-base font-bold">
              Account number
            </Label>
            <Input
              id="p-acct"
              inputMode="numeric"
              autoComplete="off"
              value={account}
              onChange={(e) => setAccount(e.target.value.replace(/\s/g, ""))}
              className="mt-1 h-12 text-base tabular"
              aria-describedby={errors.account_number ? "p-acct-error" : undefined}
              aria-invalid={!!errors.account_number}
            />
            <FieldError id="p-acct-error" msg={errors.account_number} />
          </div>
          <div>
            <Label htmlFor="p-ifsc" className="text-base font-bold">
              IFSC
            </Label>
            <Input
              id="p-ifsc"
              maxLength={11}
              value={ifsc}
              onChange={(e) => setIfsc(e.target.value.toUpperCase())}
              className="mt-1 h-12 text-base uppercase"
              aria-describedby={errors.ifsc ? "p-ifsc-error" : undefined}
              aria-invalid={!!errors.ifsc}
            />
            <FieldError id="p-ifsc-error" msg={errors.ifsc} />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              <SubmitLabel pending={create.isPending} idle="Add payee" />
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
