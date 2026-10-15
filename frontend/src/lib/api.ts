import { getAuthClient, isSupabaseConfigured } from "./supabase";
import type {
  Approval,
  ApprovalDetail,
  ApproveBody,
  Beneficiary,
  Bill,
  BillDetail,
  Biller,
  CreateBeneficiaryBody,
  CreateBillerBody,
  CreateBillBody,
  Dashboard,
  Health,
  ListResponse,
  Me,
  PayBillBody,
  PaymentAttempt,
  PaymentDetail,
  PaymentOutcome,
  Policy,
  RejectBody,
  SecurityEvent,
  UpdateBillerBody,
  UpdateBillBody,
  UpdatePolicyBody,
  WitnessReport,
} from "./types";

export class ApiError extends Error {
  code: string;
  status: number;
  request_id?: string;
  details?: Record<string, any>;
  fieldErrors?: Record<string, string>;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: Record<string, any>,
    request_id?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.request_id = request_id;
    if (details?.fields && typeof details.fields === "object") {
      this.fieldErrors = details.fields as Record<string, string>;
    }
  }
}

export function parseApiError(status: number, body: any): ApiError {
  const err = body?.error;
  const code =
    err?.code ||
    (status === 401
      ? "unauthenticated"
      : status === 403
        ? "forbidden"
        : status === 404
          ? "not_found"
          : status === 422
            ? "validation_error"
            : "internal_error");
  const message =
    err?.message || body?.message || "An unexpected error occurred.";
  return new ApiError(status, code, message, err?.details, err?.request_id);
}

export function friendlyErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    return err.message;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return "An unexpected error occurred.";
}

const unauthorizedListeners = new Set<() => void>();

export function onUnauthorized(fn: () => void): () => void {
  unauthorizedListeners.add(fn);
  return () => {
    unauthorizedListeners.delete(fn);
  };
}

function notifyUnauthorized() {
  for (const fn of unauthorizedListeners) {
    try {
      fn();
    } catch {
      // ignore
    }
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function getAuthHeader(): Promise<Record<string, string>> {
  if (typeof window !== "undefined") {
    const devToken = localStorage.getItem("keeper_dev_token");
    if (devToken) {
      return { Authorization: `Bearer ${devToken}` };
    }
    if (isSupabaseConfigured()) {
      try {
        const { data } = await getAuthClient().auth.getSession();
        if (data.session?.access_token) {
          return { Authorization: `Bearer ${data.session.access_token}` };
        }
      } catch {
        // ignore
      }
    }
  }
  return {};
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const authHeaders = await getAuthHeader();
  const headers = new Headers({
    "Content-Type": "application/json",
    ...authHeaders,
    ...((options.headers as Record<string, string>) || {}),
  });

  const url = `${API_BASE.replace(/\/$/, "")}${path}`;
  const res = await fetch(url, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    notifyUnauthorized();
  }

  const contentType = res.headers.get("content-type") || "";
  let data: any = null;
  if (contentType.includes("application/json")) {
    try {
      data = await res.json();
    } catch {
      data = null;
    }
  } else {
    data = await res.text();
  }

  if (!res.ok) {
    throw parseApiError(res.status, data);
  }

  return data as T;
}

function queryString(params?: Record<string, any>): string {
  if (!params) return "";
  const filtered = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== "",
  );
  if (filtered.length === 0) return "";
  const query = new URLSearchParams(
    filtered.map(([k, v]) => [k, String(v)]),
  ).toString();
  return query ? `?${query}` : "";
}

export const api = {
  me: () => request<Me>("/api/v1/me"),
  health: () => request<Health>("/api/v1/health"),
  dashboard: () => request<Dashboard>("/api/v1/dashboard"),

  // Bills
  getBills: (params?: {
    status?: string;
    biller_id?: string;
    limit?: number;
    offset?: number;
  }) => request<ListResponse<Bill>>(`/api/v1/bills${queryString(params)}`),
  getBill: (id: string) => request<BillDetail>(`/api/v1/bills/${id}`),
  createBill: (body: CreateBillBody) =>
    request<Bill>("/api/v1/bills", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateBill: (id: string, body: UpdateBillBody) =>
    request<Bill>(`/api/v1/bills/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  cancelBill: (id: string) =>
    request<Bill>(`/api/v1/bills/${id}/cancel`, {
      method: "POST",
    }),
  payBill: (id: string, body: PayBillBody) =>
    request<PaymentOutcome>(`/api/v1/bills/${id}/pay`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Approvals
  getApprovals: (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }) => request<ListResponse<Approval>>(`/api/v1/approvals${queryString(params)}`),
  getApproval: (id: string) => request<ApprovalDetail>(`/api/v1/approvals/${id}`),
  approveApproval: (id: string, body: ApproveBody) =>
    request<PaymentOutcome>(`/api/v1/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  rejectApproval: (id: string, body: RejectBody) =>
    request<Approval>(`/api/v1/approvals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  retryApproval: (id: string) =>
    request<PaymentOutcome>(`/api/v1/approvals/${id}/retry`, {
      method: "POST",
    }),

  // Billers & Beneficiaries
  getBillers: () => request<ListResponse<Biller>>("/api/v1/billers"),
  createBiller: (body: CreateBillerBody) =>
    request<Biller>("/api/v1/billers", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateBiller: (id: string, body: UpdateBillerBody) =>
    request<Biller>(`/api/v1/billers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  suspendBiller: (id: string) =>
    request<Biller>(`/api/v1/billers/${id}/suspend`, {
      method: "POST",
    }),
  reactivateBiller: (id: string) =>
    request<Biller>(`/api/v1/billers/${id}/reactivate`, {
      method: "POST",
    }),
  getBeneficiaries: (billerId?: string) =>
    request<ListResponse<Beneficiary>>(
      `/api/v1/beneficiaries${queryString({ biller_id: billerId })}`,
    ),
  createBeneficiary: (body: CreateBeneficiaryBody) =>
    request<Beneficiary>("/api/v1/beneficiaries", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  revokeBeneficiary: (id: string) =>
    request<Beneficiary>(`/api/v1/beneficiaries/${id}/revoke`, {
      method: "POST",
    }),

  // Policy
  getPolicy: () => request<Policy>("/api/v1/policy"),
  updatePolicy: (body: UpdatePolicyBody) =>
    request<Policy>("/api/v1/policy", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  // Payments & Witness
  getPayments: (params?: { limit?: number; offset?: number }) =>
    request<ListResponse<PaymentAttempt>>(
      `/api/v1/payments${queryString(params)}`,
    ),
  getPayment: (id: string) => request<PaymentDetail>(`/api/v1/payments/${id}`),
  getWitnessReports: (params?: { limit?: number; offset?: number }) =>
    request<ListResponse<WitnessReport>>(
      `/api/v1/witness-reports${queryString(params)}`,
    ),
  getWitnessReport: (id: string) =>
    request<WitnessReport>(`/api/v1/witness-reports/${id}`),
  verifyWitness: (body: { attempt_id?: string; bill_id?: string }) =>
    request<WitnessReport>("/api/v1/witness/verify", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // Security Events
  getSecurityEvents: (params?: {
    severity?: string;
    event_type?: string;
    limit?: number;
    offset?: number;
  }) =>
    request<ListResponse<SecurityEvent>>(
      `/api/v1/security-events${queryString(params)}`,
    ),
};
