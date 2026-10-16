// Money is always a two-decimal string. Parse only for display; never do arithmetic.

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });

export function formatMoney(value: string | null | undefined, currency = "INR"): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  if (currency === "INR") return inr.format(n);
  return new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(n);
}

export const MONEY_INPUT_RE = /^\d+(\.\d{1,2})?$/;

/** Normalize a user-entered amount like "2400" or "2400.5" to "2400.00" without floats. */
export function normalizeMoney(input: string): string | null {
  const s = input.trim().replace(/,/g, "");
  if (!MONEY_INPUT_RE.test(s)) return null;
  const [whole, frac = ""] = s.split(".");
  const w = whole.replace(/^0+(?=\d)/, "");
  return `${w}.${(frac + "00").slice(0, 2)}`;
}

/** Compare two normalized money strings without floats. Returns -1, 0, 1. */
export function compareMoney(a: string, b: string): number {
  const [aw, af] = a.split(".");
  const [bw, bf] = b.split(".");
  if (aw.length !== bw.length) return aw.length < bw.length ? -1 : 1;
  if (aw !== bw) return aw < bw ? -1 : 1;
  if (af !== bf) return af < bf ? -1 : 1;
  return 0;
}

/** Validate a money input within [min, max] (inclusive). Returns error text or null. */
export function validateMoney(
  input: string,
  opts: { min: string; max: string; positive?: boolean },
): string | null {
  if (!input.trim()) return "Please enter an amount.";
  const n = normalizeMoney(input);
  if (!n) return "Use numbers only, with up to 2 decimal places.";
  if (opts.positive && compareMoney(n, "0.00") <= 0) return "The amount must be more than ₹0.00.";
  if (compareMoney(n, opts.min) < 0) return `The amount must be at least ${formatMoney(opts.min)}.`;
  if (compareMoney(n, opts.max) > 0)
    return `The amount can't be more than ${formatMoney(opts.max)}.`;
  return null;
}
