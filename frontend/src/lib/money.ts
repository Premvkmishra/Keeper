export function formatMoney(
  amount: string | number,
  currency: string = "INR",
): string {
  const num = typeof amount === "number" ? amount : parseFloat(amount);
  if (Number.isNaN(num)) return "₹0.00";

  const formatted = new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);

  if (currency === "INR") {
    return `₹${formatted}`;
  }
  return `${currency} ${formatted}`;
}

export function normalizeMoney(val: string): string | null {
  const trimmed = val.trim();
  if (!trimmed) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) {
    return null;
  }
  const num = parseFloat(trimmed);
  if (Number.isNaN(num)) return null;
  return num.toFixed(2);
}

export function validateMoney(
  val: string,
  opts?: { min?: string; max?: string; positive?: boolean },
): string | null {
  const norm = normalizeMoney(val);
  if (norm === null) {
    return "Enter a valid amount with up to two decimals.";
  }
  const num = parseFloat(norm);
  if (opts?.positive && num <= 0) {
    return "Amount must be greater than zero.";
  }
  if (opts?.min !== undefined && num < parseFloat(opts.min)) {
    return `Amount must be at least ₹${opts.min}.`;
  }
  if (opts?.max !== undefined && num > parseFloat(opts.max)) {
    return `Amount cannot exceed ₹${opts.max}.`;
  }
  return null;
}
