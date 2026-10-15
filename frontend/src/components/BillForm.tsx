import { useState, type FormEvent, type ReactNode } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorSummary, FieldError, SubmitLabel, ConfirmDialog } from "@/components/common";
import { ApiError, friendlyErrorMessage } from "@/lib/api";
import { BILLER_CATEGORY } from "@/lib/format";
import { normalizeMoney, validateMoney } from "@/lib/money";
import { useBillers, useCreateBill, useUpdateBill } from "@/lib/queries";
import type { Bill, BillerCategory, UpdateBillBody } from "@/lib/types";

export const ACCOUNT_RE = /^[0-9]{9,18}$/;
export const IFSC_RE = /^[A-Z]{4}0[A-Z0-9]{6}$/;

type Values = {
  title: string;
  category: BillerCategory;
  amount: string;
  due_date: string;
  invoice_ref: string;
  biller_id: string;
  destination_account_number: string;
  destination_ifsc: string;
};

const selectClass = "mt-1 h-12 w-full rounded-md border border-input bg-card px-3 text-base";

function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <Label htmlFor={id} className="text-base font-bold">
        {label}
      </Label>
      {children}
      {hint && <p className="mt-1 text-muted-foreground">{hint}</p>}
      <FieldError id={`${id}-error`} msg={error} />
    </div>
  );
}

export function BillFormDialog({
  open,
  onOpenChange,
  bill,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  bill?: Bill;
}) {
  const editing = !!bill;
  const billers = useBillers();
  const create = useCreateBill();
  const update = useUpdateBill(bill?.id ?? "");
  const [v, setV] = useState<Values>({
    title: bill?.title ?? "",
    category: bill?.category ?? "electricity",
    amount: bill?.amount ?? "",
    due_date: bill?.due_date ?? "",
    invoice_ref: bill?.invoice_ref ?? "",
    biller_id: bill?.biller_id ?? "",
    destination_account_number: "",
    destination_ifsc: bill?.destination_ifsc ?? "",
  });
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [errors, setErrors] = useState<Partial<Record<keyof Values, string>>>({});
  const [formError, setFormError] = useState<unknown>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pending = create.isPending || update.isPending;

  const set = (k: keyof Values) => (val: string) => setV((s) => ({ ...s, [k]: val }));

  function validate(): Partial<Record<keyof Values, string>> {
    const e: Partial<Record<keyof Values, string>> = {};
    if (!v.title.trim()) e.title = "Please enter a title.";
    else if (v.title.length > 120) e.title = "The title can be at most 120 characters.";
    const m = validateMoney(v.amount, { min: "0.00", max: "10000000.00", positive: true });
    if (m) e.amount = m;
    if (!v.due_date) e.due_date = "Please choose a due date.";
    if (v.invoice_ref.length > 64)
      e.invoice_ref = "The invoice reference can be at most 64 characters.";
    const needDest =
      !editing ||
      v.destination_account_number !== "" ||
      v.destination_ifsc !== bill?.destination_ifsc;
    if (needDest) {
      if (!ACCOUNT_RE.test(v.destination_account_number))
        e.destination_account_number = "Enter the full account number: 9 to 18 digits.";
      if (!IFSC_RE.test(v.destination_ifsc))
        e.destination_ifsc = "IFSC looks like ABCD0123456 (11 characters).";
    }
    return e;
  }

  function buildPatch(): UpdateBillBody {
    if (!bill) return {};
    const p: UpdateBillBody = {};
    if (v.title.trim() !== bill.title) p.title = v.title.trim();
    const amt = normalizeMoney(v.amount);
    if (amt && amt !== bill.amount) p.amount = amt;
    if (v.due_date !== bill.due_date) p.due_date = v.due_date;
    if ((v.biller_id || null) !== bill.biller_id) p.biller_id = v.biller_id || null;
    if (v.destination_account_number || v.destination_ifsc !== bill.destination_ifsc) {
      p.destination_account_number = v.destination_account_number;
      p.destination_ifsc = v.destination_ifsc;
    }
    return p;
  }

  function handleApiError(err: unknown) {
    if (err instanceof ApiError && err.code === "validation_error") {
      setErrors(err.fieldErrors as Partial<Record<keyof Values, string>>);
    }
    setFormError(err);
    toast.error(friendlyErrorMessage(err));
  }

  async function doSave() {
    setFormError(null);
    try {
      if (editing && bill) {
        const patch = buildPatch();
        if (Object.keys(patch).length === 0) {
          onOpenChange(false);
          return;
        }
        await update.mutateAsync(patch);
        toast.success("Bill updated.");
      } else {
        await create.mutateAsync({
          body: {
            title: v.title.trim(),
            category: v.category,
            amount: normalizeMoney(v.amount) as string,
            currency: "INR",
            due_date: v.due_date,
            ...(v.invoice_ref.trim() ? { invoice_ref: v.invoice_ref.trim() } : {}),
            biller_id: v.biller_id || null,
            destination_account_number: v.destination_account_number,
            destination_ifsc: v.destination_ifsc,
          },
          file: documentFile,
        });
        toast.success(documentFile ? "Bill and document saved." : "Bill added.");
      }
      setConfirmOpen(false);
      onOpenChange(false);
    } catch (err) {
      setConfirmOpen(false);
      handleApiError(err);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length) return;
    if (editing) setConfirmOpen(true);
    else void doSave();
  }

  const desc = (k: keyof Values) => (errors[k] ? `${k}-error` : undefined);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-xl">{editing ? "Edit this bill" : "Add a bill"}</DialogTitle>
          <DialogDescription className="text-base text-muted-foreground">
            Enter the details exactly as they appear on the bill.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} noValidate className="space-y-4" aria-live="polite">
          <ErrorSummary errors={errors} />
          {formError &&
          !(formError instanceof ApiError && formError.code === "validation_error") ? (
            <p role="alert" className="rounded-md bg-danger-bg p-3 font-bold text-danger">
              {friendlyErrorMessage(formError)}
            </p>
          ) : null}
          <Field id="title" label="Title" error={errors.title}>
            <Input
              id="title"
              value={v.title}
              maxLength={120}
              onChange={(e) => set("title")(e.target.value)}
              className="mt-1 h-12 text-base"
              aria-describedby={desc("title")}
              aria-invalid={!!errors.title}
            />
          </Field>
          {!editing && (
            <Field id="category" label="Category">
              <select
                id="category"
                className={selectClass}
                value={v.category}
                onChange={(e) => set("category")(e.target.value)}
              >
                {(Object.keys(BILLER_CATEGORY) as BillerCategory[]).map((c) => (
                  <option key={c} value={c}>
                    {BILLER_CATEGORY[c]}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field id="amount" label="Amount (₹)" error={errors.amount}>
            <Input
              id="amount"
              inputMode="decimal"
              value={v.amount}
              onChange={(e) => set("amount")(e.target.value)}
              onBlur={() => {
                const n = normalizeMoney(v.amount);
                if (n) set("amount")(n);
              }}
              className="mt-1 h-12 text-base tabular"
              aria-describedby={desc("amount")}
              aria-invalid={!!errors.amount}
            />
          </Field>
          <Field id="due_date" label="Due date" error={errors.due_date}>
            <Input
              id="due_date"
              type="date"
              value={v.due_date}
              onChange={(e) => set("due_date")(e.target.value)}
              className="mt-1 h-12 text-base"
              aria-describedby={desc("due_date")}
              aria-invalid={!!errors.due_date}
            />
          </Field>
          <Field id="biller_id" label="Biller">
            <select
              id="biller_id"
              className={selectClass}
              value={v.biller_id}
              onChange={(e) => set("biller_id")(e.target.value)}
            >
              <option value="">No biller / unknown</option>
              {(billers.data?.items ?? []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                  {b.status === "suspended" ? " (paused)" : ""}
                </option>
              ))}
            </select>
          </Field>
          {!editing && (
            <Field id="invoice_ref" label="Invoice reference (optional)" error={errors.invoice_ref}>
              <Input
                id="invoice_ref"
                value={v.invoice_ref}
                maxLength={64}
                onChange={(e) => set("invoice_ref")(e.target.value)}
                className="mt-1 h-12 text-base"
                aria-describedby={desc("invoice_ref")}
              />
            </Field>
          )}
          {!editing && (
            <Field
              id="bill-document"
              label="Attach bill document (optional)"
              hint="PDF, JPEG, or PNG. Maximum 5 MB."
            >
              <Input
                id="bill-document"
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                onChange={(e) => setDocumentFile(e.target.files?.[0] ?? null)}
                className="mt-1 h-12 text-base file:mr-3 file:rounded file:border-0 file:bg-muted file:px-3 file:py-1"
              />
            </Field>
          )}
          <Field
            id="destination_account_number"
            label="Payee account number"
            error={errors.destination_account_number}
            hint={
              editing
                ? `Currently ${bill?.destination_account_number_masked}. Leave empty to keep it.`
                : "9 to 18 digits."
            }
          >
            <Input
              id="destination_account_number"
              inputMode="numeric"
              autoComplete="off"
              value={v.destination_account_number}
              onChange={(e) => set("destination_account_number")(e.target.value.replace(/\s/g, ""))}
              className="mt-1 h-12 text-base tabular"
              aria-describedby={desc("destination_account_number")}
              aria-invalid={!!errors.destination_account_number}
            />
          </Field>
          <Field id="destination_ifsc" label="Payee IFSC" error={errors.destination_ifsc}>
            <Input
              id="destination_ifsc"
              value={v.destination_ifsc}
              maxLength={11}
              onChange={(e) => set("destination_ifsc")(e.target.value.toUpperCase())}
              className="mt-1 h-12 text-base uppercase"
              aria-describedby={desc("destination_ifsc")}
              aria-invalid={!!errors.destination_ifsc}
            />
          </Field>
          <div className="flex flex-wrap justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              <SubmitLabel pending={pending} idle={editing ? "Save changes" : "Add bill"} />
            </Button>
          </div>
        </form>
        <ConfirmDialog
          open={confirmOpen}
          onOpenChange={setConfirmOpen}
          title="Save these changes?"
          description="Changing the amount or payee cancels any approval already given."
          confirmLabel="Save changes"
          pending={pending}
          onConfirm={() => void doSave()}
        />
      </DialogContent>
    </Dialog>
  );
}
