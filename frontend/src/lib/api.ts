import { getAuthClient, getAuthToken, isSupabaseConfigured } from "./supabase";
import type {
  Approval,
  ApprovalDetail,
  ApproveBody,
  AuthResponse,
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
  LoginBody,
  Me,
  PayBillBody,
  PaymentAttempt,
  PaymentDetail,
  PaymentOutcome,
  Policy,
  RegisterBody,
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
    statusOrObj:
      | number
      | {
          status: number;
          code: string;
          message: string;
          details?: Record<string, any>;
          request_id?: string;
        },
    code?: string,
    message?: string,
    details?: Record<string, any>,
    request_id?: string,
  ) {
    if (typeof statusOrObj === "object") {
      super(statusOrObj.message);
      this.name = "ApiError";
      this.status = statusOrObj.status;
      this.code = statusOrObj.code;
      this.details = statusOrObj.details;
      this.request_id = statusOrObj.request_id;
    } else {
      super(message ?? "API Error");
      this.name = "ApiError";
      this.status = statusOrObj;
      this.code = code ?? "unknown";
      this.details = details;
      this.request_id = request_id;
    }
    if (this.details?.fields && typeof this.details.fields === "object") {
      this.fieldErrors = this.details.fields as Record<string, string>;
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
    const token = getAuthToken();
    if (token) {
      return { Authorization: `Bearer ${token}` };
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
    credentials: "include",
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
  createBill: async (body: CreateBillBody, file?: File | null) => {
    if (file) {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", body.title);
      formData.append("category", body.category);
      formData.append("amount", body.amount);
      formData.append("due_date", body.due_date);
      formData.append("destination_account_number", body.destination_account_number);
      formData.append("destination_ifsc", body.destination_ifsc);
      if (body.invoice_ref) formData.append("invoice_ref", body.invoice_ref);
      if (body.biller_id) formData.append("biller_id", body.biller_id);

      const authHeaders = await getAuthHeader();
      const url = `${API_BASE.replace(/\/$/, "")}/api/v1/bills/upload`;
      const res = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: {
          ...authHeaders,
        },
        body: formData,
      });

      if (!res.ok) {
        let errData: any = null;
        try {
          errData = await res.json();
        } catch {
          errData = null;
        }
        throw parseApiError(res.status, errData);
      }
      return (await res.json()) as Bill;
    }

    const payload: Record<string, any> = { ...body };
    if (!payload.biller_id) delete payload.biller_id;
    if (!payload.invoice_ref) delete payload.invoice_ref;

    return request<Bill>("/api/v1/bills", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateBill: (id: string, body: UpdateBillBody) =>
    request<Bill>(`/api/v1/bills/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  cancelBill: (id: string) =>
    request<Bill>(`/api/v1/bills/${id}/cancel`, {
      method: "POST",
    }),
  payBill: (id: string, body?: PayBillBody | string) => {
    const payload: PayBillBody =
      typeof body === "string"
        ? { idempotency_key: body }
        : body && body.idempotency_key
          ? body
          : { idempotency_key: crypto.randomUUID() };
    return request<PaymentOutcome>(`/api/v1/bills/${id}/pay`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Approvals
  getApprovals: (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }) => request<ListResponse<Approval>>(`/api/v1/approvals${queryString(params)}`),
  getApproval: (id: string) => request<ApprovalDetail>(`/api/v1/approvals/${id}`),
  approveApproval: (id: string, body: ApproveBody) =>
    request<Approval>(`/api/v1/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  rejectApproval: (id: string, body: RejectBody) =>
    request<Approval>(`/api/v1/approvals/${id}/reject`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  retryApproval: (id: string) =>
    request<Approval>(`/api/v1/approvals/${id}/retry`, {
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
  getPayments: (params?: {
    status?: string;
    bill_id?: string;
    limit?: number;
    offset?: number;
  }) =>
    request<ListResponse<PaymentAttempt>>(
      `/api/v1/payments${queryString(params)}`,
    ),
  getPayment: (id: string) => request<PaymentDetail>(`/api/v1/payments/${id}`),
  getWitnessReports: (params?: {
    verdict?: string;
    bill_id?: string;
    limit?: number;
    offset?: number;
  }) =>
    request<ListResponse<WitnessReport>>(
      `/api/v1/witness-reports${queryString(params)}`,
    ),
  getWitnessReport: (id: string) =>
    request<WitnessReport>(`/api/v1/witness-reports/${id}`),
  verifyWitness: (body: string | { attempt_id?: string; bill_id?: string }) => {
    const payload = typeof body === "string" ? { attempt_id: body } : body;
    if (payload.attempt_id) {
      return request<WitnessReport>(
        `/api/v1/payments/${payload.attempt_id}/witness-verify`,
        {
          method: "POST",
        },
      );
    }
    return request<WitnessReport>("/api/v1/witness/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

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

  // Authentication
  login: (body: LoginBody) =>
    request<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  register: (body: RegisterBody) =>
    request<AuthResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  logout: () =>
    request<{ message: string }>("/api/v1/auth/logout", {
      method: "POST",
    }),
};
