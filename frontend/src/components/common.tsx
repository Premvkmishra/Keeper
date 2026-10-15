import { useEffect, useRef, useState, type ReactNode } from "react";
import { ChevronDown, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { ApiError, friendlyErrorMessage } from "@/lib/api";
import { cn } from "@/lib/utils";
import { PAGE_SIZE } from "@/lib/queries";

export function PageHeader({
  title,
  intro,
  action,
}: {
  title: string;
  intro?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1>{title}</h1>
        {intro && <p className="mt-1 text-muted-foreground">{intro}</p>}
      </div>
      {action}
    </div>
  );
}

export function Panel({
  title,
  children,
  className,
  action,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <section className={cn("rounded-lg border bg-card p-5", className)}>
      {(title || action) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-xl">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-24 w-full rounded-lg bg-surface-alt" />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function EmptyState({ text, action }: { text: string; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed bg-card p-8 text-center">
      <p className="text-muted-foreground">{text}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function TechDetails({
  children,
  label = "Technical details",
}: {
  children: ReactNode;
  label?: string;
}) {
  return (
    <details className="group mt-3 rounded-md border bg-surface-alt px-4 py-2">
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 font-bold text-muted-foreground">
        <ChevronDown aria-hidden className="size-5 transition-transform group-open:rotate-180" />
        {label}
      </summary>
      <div className="pb-2 pt-1 text-base break-all">{children}</div>
    </details>
  );
}

export function KV({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex flex-wrap gap-x-2">
      <dt className="font-bold">{k}:</dt>
      <dd className="font-mono text-sm leading-7">{v ?? "—"}</dd>
    </div>
  );
}

export function ErrorAlert({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-lg border border-danger/40 bg-danger-bg p-4 text-danger">
      <p className="font-bold">{friendlyErrorMessage(error)}</p>
      {onRetry && (
        <Button variant="outline" className="mt-3" onClick={onRetry}>
          Try again
        </Button>
      )}
      {error instanceof ApiError && error.request_id && (
        <TechDetails>
          <dl>
            <KV k="Error code" v={error.code} />
            <KV k="Request ID" v={error.request_id} />
          </dl>
        </TechDetails>
      )}
    </div>
  );
}

export function Pagination({
  offset,
  total,
  onChange,
}: {
  offset: number;
  total: number;
  onChange: (o: number) => void;
}) {
  if (total <= PAGE_SIZE) return null;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return (
    <nav aria-label="Pages" className="mt-6 flex items-center justify-between gap-3">
      <Button
        variant="outline"
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - PAGE_SIZE))}
      >
        Previous
      </Button>
      <span className="tabular">
        Page {page} of {pages}
      </span>
      <Button
        variant="outline"
        disabled={offset + PAGE_SIZE >= total}
        onClick={() => onChange(offset + PAGE_SIZE)}
      >
        Next
      </Button>
    </nav>
  );
}

export function FilterChips<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: T | undefined; label: string }[];
  value: T | undefined;
  onChange: (v: T | undefined) => void;
}) {
  return (
    <div role="group" aria-label={label} className="mb-5 flex flex-wrap gap-2">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.label}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "min-h-11 rounded-full border px-4 font-bold transition-colors",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : "bg-card text-foreground hover:bg-accent",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function ListBody<T>({
  query,
  empty,
  render,
}: {
  query: { isLoading: boolean; error: unknown; data?: { items: T[] }; refetch: () => unknown };
  empty: ReactNode;
  render: (items: T[]) => ReactNode;
}) {
  if (query.isLoading) return <ListSkeleton />;
  if (query.error) return <ErrorAlert error={query.error} onRetry={() => query.refetch()} />;
  const items = query.data?.items ?? [];
  if (items.length === 0) return <>{empty}</>;
  return <>{render(items)}</>;
}

export function SubmitLabel({
  pending,
  idle,
  busy = "Saving…",
}: {
  pending: boolean;
  idle: string;
  busy?: string;
}) {
  return pending ? (
    <>
      <Loader2 aria-hidden className="animate-spin" />
      {busy}
    </>
  ) : (
    <>{idle}</>
  );
}

/** Confirmation for destructive/irreversible actions. Default focus is on the safe (cancel) button. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = "Go back",
  destructive,
  pending,
  onConfirm,
  children,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  pending?: boolean;
  onConfirm: () => void;
  children?: ReactNode;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent
        onOpenAutoFocus={(e) => {
          e.preventDefault();
          cancelRef.current?.focus();
        }}
      >
        <AlertDialogHeader>
          <AlertDialogTitle className="text-xl">{title}</AlertDialogTitle>
          {description && (
            <AlertDialogDescription className="text-base text-muted-foreground">
              {description}
            </AlertDialogDescription>
          )}
        </AlertDialogHeader>
        {children}
        <AlertDialogFooter className="gap-2">
          <AlertDialogCancel ref={cancelRef} className="min-h-12 text-base">
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={pending}
            onClick={(e) => {
              e.preventDefault();
              onConfirm();
            }}
            className={cn(
              "min-h-12 text-base font-bold",
              destructive
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                : "",
            )}
          >
            <SubmitLabel pending={!!pending} idle={confirmLabel} busy="Working…" />
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function useNow(intervalMs = 60_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function FieldError({ id, msg }: { id: string; msg?: string }) {
  if (!msg) return null;
  return (
    <p id={id} className="mt-1 font-bold text-danger">
      {msg}
    </p>
  );
}

export function ErrorSummary({ errors }: { errors: Record<string, string | undefined> }) {
  const entries = Object.entries(errors).filter(([, v]) => Boolean(v)) as [string, string][];
  if (entries.length === 0) return null;
  return (
    <div role="alert" className="rounded-md border border-danger/40 bg-danger-bg p-3 text-danger">
      <p className="font-bold">Please fix {entries.length === 1 ? "this" : "these"}:</p>
      <ul className="ml-5 list-disc">
        {entries.map(([k, m], index) => (
          <li key={`${k}-${index}-${m}`}>{m}</li>
        ))}
      </ul>
    </div>
  );
}
