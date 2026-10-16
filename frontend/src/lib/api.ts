import { getAccessToken } from "./supabase";
import type {
  Approval,
  ApprovalDetail,
  ApprovalStatus,
  AttemptStatus,
  Beneficiary,
  BeneficiaryStatus,
  Bill,
  BillDetail,
  Biller,
  BillStatus,
  CreateBeneficiaryBody,
  CreateBillBody,
  CreateBillerBody,
  Dashboard,
  ErrorCode,
  Health,
  ListResponse,
  Me,
  PaymentAttempt,
  PaymentDetail,
  PaymentOutcome,
  Policy,
  SecurityEvent,
  SecurityEventType,
  Severity,
  UpdateBillBody,
  UpdateBillerBody,
  UpdatePolicyBody,
  WitnessReport,
  WitnessVerdict,
} from "./types";

export class ApiError extends Error {
  code: ErrorCode | "network_error";
  details: Record<string, unknown>;
  request_id: string | null;
  status: number;
  constructor(init: {
    code: ApiError["code"];
    message: string;
    details?: Record<string, unknown>;
    request_id?: string | null;
    status: number;
  }) {
    super(init.message);
    this.name = "ApiError";
    this.code = init.code;
    this.details = init.details ?? {};
    this.request_id = init.request_id ?? null;
    this.status = init.status;
  }

  get fieldErrors(): Record<string, string> {
    const f = this.details["fields"];
    return f && typeof f === "object" ? (f as Record<string, string>) : {};
  }
}

export function parseApiError(status: number, body: unknown): ApiError {
  if (body && typeof body === "object" && "error" in body) {
    const e = (body as { error: unknown }).error;
    if (e && typeof e === "object") {
      const o = e as Record<string, unknown>;
      return new ApiError({
        code: (typeof o.code === "string" ? o.code : "internal_error") as ErrorCode,
        message: typeof o.message === "string" ? o.message : "Something went wrong.",
        details:
          o.details && typeof o.details === "object" ? (o.details as Record<string, unknown>) : {},
        request_id: typeof o.request_id === "string" ? o.request_id : null,
        status,
      });
    }
  }
  return new ApiError({
    code: status === 401 ? "unauthenticated" : status === 403 ? "forbidden" : "internal_error",
    message: "Something went wrong. Please try again.",
    status,
  });
}

let unauthorizedHandler: (() => void) | null = null;
export function onUnauthorized(fn: () => void) {
  unauthorizedHandler = fn;
}

function baseUrl(): string {
  const b = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
  return `${b.replace(/\/$/, "")}/api/v1`;
}

type Query = Record<string, string | number | null | undefined>;

function qs(q?: Query): string {
  if (!q) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q))
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function request<T>(
  method: "GET" | "POST" | "PATCH" | "PUT",
  path: string,
  opts: { query?: Query; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const isMultipart = typeof FormData !== "undefined" && opts.body instanceof FormData;
  if (opts.body !== undefined && !isMultipart) headers["Content-Type"] = "application/json";
  if (opts.auth !== false) {
    const token = await getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  let res: Response;
  try {
    res = await fetch(`${baseUrl()}${path}${qs(opts.query)}`, {
      method,
      headers,
      body:
        opts.body === undefined
          ? undefined
          : isMultipart
            ? (opts.body as FormData)
            : JSON.stringify(opts.body),
    });
  } catch {
    throw new ApiError({
      code: "network_error",
      message: "We couldn't reach Keeper. Please check your connection and try again.",
      status: 0,
    });
  }
  const text = await res.text();
  let json: unknown = null;
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = null;
    }
  }
  if (!res.ok) {
    const err = parseApiError(res.status, json);
    if (res.status === 401 && opts.auth !== false) unauthorizedHandler?.();
    throw err;
  }
  return json as T;
}

type Page = { limit?: number; offset?: number };

export const api = {
  // 4.1
  health: () => request<Health>("GET", "/health", { auth: false }),
  bootstrapHousehold: (body: { household_name: string; display_name: string }) =>
    request<{ user_id: string; email: string; display_name: string; role: string }>(
      "POST",
      "/auth/household",
      { body },
    ),
  me: () => request<Me>("GET", "/me"),
  // 4.2
  dashboard: () => request<Dashboard>("GET", "/dashboard"),
  // 4.3
  listBills: (q: Page & { status?: BillStatus } = {}) =>
    request<ListResponse<Bill>>("GET", "/bills", { query: q }),
  createBill: (body: CreateBillBody) => request<Bill>("POST", "/bills", { body }),
  uploadBill: (body: CreateBillBody, file: File) => {
    const form = new FormData();
    for (const [key, value] of Object.entries(body)) {
      if (value !== null && value !== undefined) form.append(key, String(value));
    }
    form.append("file", file);
    return request<Bill>("POST", "/bills/upload", { body: form });
  },
  getBill: (id: string) => request<BillDetail>("GET", `/bills/${id}`),
  updateBill: (id: string, body: UpdateBillBody) =>
    request<Bill>("PATCH", `/bills/${id}`, { body }),
  cancelBill: (id: string) => request<Bill>("POST", `/bills/${id}/cancel`, { body: {} }),
  payBill: (id: string, idempotency_key: string) =>
    request<PaymentOutcome>("POST", `/bills/${id}/pay`, { body: { idempotency_key } }),
  // 4.4
  listApprovals: (q: Page & { status?: ApprovalStatus } = {}) =>
    request<ListResponse<Approval>>("GET", "/approvals", { query: q }),
  getApproval: (id: string) => request<ApprovalDetail>("GET", `/approvals/${id}`),
  approve: (id: string, body: { details_hash: string; note?: string }) =>
    request<Approval>("POST", `/approvals/${id}/approve`, { body }),
  retryApproval: (id: string) => request<Approval>("POST", `/approvals/${id}/retry`, { body: {} }),
  reject: (id: string, body: { note?: string }) =>
    request<Approval>("POST", `/approvals/${id}/reject`, { body }),
  // 4.5
  listBillers: (q: Page = {}) => request<ListResponse<Biller>>("GET", "/billers", { query: q }),
  createBiller: (body: CreateBillerBody) => request<Biller>("POST", "/billers", { body }),
  updateBiller: (id: string, body: UpdateBillerBody) =>
    request<Biller>("PATCH", `/billers/${id}`, { body }),
  suspendBiller: (id: string) => request<Biller>("POST", `/billers/${id}/suspend`, { body: {} }),
  reactivateBiller: (id: string) =>
    request<Biller>("POST", `/billers/${id}/reactivate`, { body: {} }),
  listBeneficiaries: (q: Page & { biller_id?: string; status?: BeneficiaryStatus } = {}) =>
    request<ListResponse<Beneficiary>>("GET", "/beneficiaries", { query: q }),
  createBeneficiary: (body: CreateBeneficiaryBody) =>
    request<Beneficiary>("POST", "/beneficiaries", { body }),
  revokeBeneficiary: (id: string) =>
    request<Beneficiary>("POST", `/beneficiaries/${id}/revoke`, { body: {} }),
  // 4.6
  listPayments: (q: Page & { status?: AttemptStatus; bill_id?: string } = {}) =>
    request<ListResponse<PaymentAttempt>>("GET", "/payments", { query: q }),
  getPayment: (id: string) => request<PaymentDetail>("GET", `/payments/${id}`),
  listSecurityEvents: (
    q: Page & {
      severity?: Severity;
      event_type?: SecurityEventType;
      bill_id?: string;
      attempt_id?: string;
    } = {},
  ) => request<ListResponse<SecurityEvent>>("GET", "/security-events", { query: q }),
  listWitnessReports: (q: Page & { verdict?: WitnessVerdict; bill_id?: string } = {}) =>
    request<ListResponse<WitnessReport>>("GET", "/witness-reports", { query: q }),
  getWitnessReport: (id: string) => request<WitnessReport>("GET", `/witness-reports/${id}`),
  witnessVerify: (attemptId: string) =>
    request<WitnessReport>("POST", `/payments/${attemptId}/witness-verify`, { body: {} }),
  // 4.7
  getPolicy: () => request<Policy>("GET", "/policy"),
  updatePolicy: (body: UpdatePolicyBody) => request<Policy>("PUT", "/policy", { body }),
};

export function friendlyErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "dependency_unavailable")
      return "A required safety service isn't available, so nothing was paid.";
    if (e.code === "forbidden") return "You don't have permission to do this.";
    if (e.code === "approval_expired") return "This approval has expired. Nothing was paid.";
    if (e.code === "approval_details_changed")
      return "The bill changed after this approval was requested. Nothing was paid. Please review it again.";
    if (e.code === "approval_not_pending")
      return "This approval is no longer waiting for a decision. Nothing was paid. Please review it again.";
    return e.message;
  }
  return "Something went wrong. Please try again.";
}
