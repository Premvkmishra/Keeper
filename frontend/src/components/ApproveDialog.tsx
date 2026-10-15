import { useRef, useState } from "react";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { SubmitLabel } from "@/components/common";
import { formatMoney } from "@/lib/money";
import type { Approval } from "@/lib/types";

export function ApproveDialog({
  approval,
  open,
  onOpenChange,
  pending,
  onConfirm,
}: {
  approval: Approval;
  open: boolean;
  onOpenChange: (o: boolean) => void;
  pending: boolean;
  onConfirm: (note: string | undefined) => void;
}) {
  const [checked, setChecked] = useState(false);
  const [note, setNote] = useState("");
  const cancelRef = useRef<HTMLButtonElement>(null);
  const amount = formatMoney(approval.amount, approval.currency);

  return (
    <AlertDialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setChecked(false);
          setNote("");
        }
        onOpenChange(o);
      }}
    >
      <AlertDialogContent
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          cancelRef.current?.focus();
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle className="text-xl">Approve and pay {amount}?</AlertDialogTitle>
          <AlertDialogDescription className="text-base text-muted-foreground">
            Please check these details one more time.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <dl className="space-y-1 rounded-md border bg-surface-alt p-4">
          <div>
            <dt className="inline font-bold">Amount: </dt>
            <dd className="inline money-lg">{amount}</dd>
          </div>
          <div>
            <dt className="inline font-bold">Payee account: </dt>
            <dd className="inline">{approval.destination_account_number_masked}</dd>
          </div>
          <div>
            <dt className="inline font-bold">IFSC: </dt>
            <dd className="inline">{approval.destination_ifsc}</dd>
          </div>
          <div>
            <dt className="inline font-bold">Bill: </dt>
            <dd className="inline">{approval.bill_title}</dd>
          </div>
        </dl>
        <div>
          <Label htmlFor="approve-note" className="text-base font-bold">
            Note (optional)
          </Label>
          <Textarea
            id="approve-note"
            maxLength={500}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="mt-1 text-base"
          />
        </div>
        <div className="flex items-start gap-3">
          <Checkbox
            id="approve-check"
            checked={checked}
            onCheckedChange={(v) => setChecked(v === true)}
            className="mt-1 size-6"
          />
          <Label htmlFor="approve-check" className="text-base leading-snug">
            I have checked the amount and payee
          </Label>
        </div>
        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel ref={cancelRef} className="min-h-12 text-base">
            Go back
          </AlertDialogCancel>
          <Button
            disabled={!checked || pending}
            onClick={() => onConfirm(note.trim() || undefined)}
          >
            <SubmitLabel pending={pending} idle={`Approve and pay ${amount}`} busy="Paying…" />
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
