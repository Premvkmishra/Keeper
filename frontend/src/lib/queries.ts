import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { api } from "./api";
import type {
  ApprovalStatus,
  AttemptStatus,
  BeneficiaryStatus,
  BillStatus,
  CreateBeneficiaryBody,
  CreateBillBody,
  CreateBillerBody,
  SecurityEventType,
  Severity,
  UpdateBillBody,
  UpdateBillerBody,
  UpdatePolicyBody,
  WitnessVerdict,
} from "./types";

export const PAGE_SIZE = 25;

export const qk = {
  health: ["health"] as const,
  me: ["me"] as const,
  dashboard: ["dashboard"] as const,
  bills: (p?: object) => ["bills", p ?? {}] as const,
  bill: (id: string) => ["bill", id] as const,
  approvals: (p?: object) => ["approvals", p ?? {}] as const,
  approval: (id: string) => ["approval", id] as const,
  pendingCount: ["approvals", "pending-count"] as const,
  billers: (p?: object) => ["billers", p ?? {}] as const,
  beneficiaries: (p?: object) => ["beneficiaries", p ?? {}] as const,
  payments: (p?: object) => ["payments", p ?? {}] as const,
  payment: (id: string) => ["payment", id] as const,
  security: (p?: object) => ["security", p ?? {}] as const,
  witnessReports: (p?: object) => ["witness", p ?? {}] as const,
  witnessReport: (id: string) => ["witness-report", id] as const,
  policy: ["policy"] as const,
};

const PAYMENT_KEYS = [
  "bills",
  "bill",
  "approvals",
  "approval",
  "payments",
  "payment",
  "security",
  "witness",
  "witness-report",
  "dashboard",
];

function useInvalidate(keys: string[] = PAYMENT_KEYS) {
  const qc = useQueryClient();
  return () => Promise.all(keys.map((k) => qc.invalidateQueries({ queryKey: [k] })));
}

// ---- Reads ----
export const useHealth = () =>
  useQuery({ queryKey: qk.health, queryFn: api.health, refetchInterval: 60_000, retry: false });
export const useDashboard = () => useQuery({ queryKey: qk.dashboard, queryFn: api.dashboard });

export const useBills = (p: { status?: BillStatus; offset: number }) =>
  useQuery({
    queryKey: qk.bills(p),
    queryFn: () => api.listBills({ ...p, limit: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
export const useBill = (id: string) =>
  useQuery({ queryKey: qk.bill(id), queryFn: () => api.getBill(id) });

export const useApprovals = (p: { status?: ApprovalStatus; offset: number }) =>
  useQuery({
    queryKey: qk.approvals(p),
    queryFn: () => api.listApprovals({ ...p, limit: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
export const useApproval = (id: string) =>
  useQuery({
    queryKey: qk.approval(id),
    queryFn: () => api.getApproval(id),
    refetchInterval: (query) =>
      query.state.data?.approval.processing_status === "processing" ? 2_000 : false,
  });
export const usePendingApprovalCount = (enabled: boolean) =>
  useQuery({
    queryKey: qk.pendingCount,
    queryFn: () => api.listApprovals({ status: "pending", limit: 1 }),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    enabled,
  });

export const useBillers = () =>
  useQuery({
    queryKey: qk.billers({ limit: 100 }),
    queryFn: () => api.listBillers({ limit: 100 }),
  });
export const useBeneficiaries = (p: { biller_id?: string; status?: BeneficiaryStatus } = {}) =>
  useQuery({
    queryKey: qk.beneficiaries(p),
    queryFn: () => api.listBeneficiaries({ ...p, limit: 100 }),
  });

export const usePayments = (p: { status?: AttemptStatus; offset: number }) =>
  useQuery({
    queryKey: qk.payments(p),
    queryFn: () => api.listPayments({ ...p, limit: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
export const usePayment = (id: string | null) =>
  useQuery({
    queryKey: qk.payment(id ?? ""),
    queryFn: () => api.getPayment(id as string),
    enabled: !!id,
  });

export const useSecurityEvents = (p: {
  severity?: Severity;
  event_type?: SecurityEventType;
  offset: number;
}) =>
  useQuery({
    queryKey: qk.security(p),
    queryFn: () => api.listSecurityEvents({ ...p, limit: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

export const useWitnessReports = (p: { verdict?: WitnessVerdict; offset: number }) =>
  useQuery({
    queryKey: qk.witnessReports(p),
    queryFn: () => api.listWitnessReports({ ...p, limit: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });
export const useWitnessReport = (id: string | null, enabled = true) =>
  useQuery({
    queryKey: qk.witnessReport(id ?? ""),
    queryFn: () => api.getWitnessReport(id as string),
    enabled: !!id && enabled,
  });

export const usePolicy = () => useQuery({ queryKey: qk.policy, queryFn: api.getPolicy });
// ---- Mutations ----
export function useCreateBill() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ body, file }: { body: CreateBillBody; file?: File | null }) =>
      file ? api.uploadBill(body, file) : api.createBill(body),
    onSuccess: () => inv(),
  });
}
export function useUpdateBill(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (b: UpdateBillBody) => api.updateBill(id, b),
    onSuccess: () => inv(),
  });
}
export function useCancelBill(id: string) {
  const inv = useInvalidate();
  return useMutation({ mutationFn: () => api.cancelBill(id), onSuccess: () => inv() });
}
export function usePayBill(id: string) {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (key: string) => api.payBill(id, key), onSettled: () => inv() });
}
export function useApproveApproval(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (b: { details_hash: string; note?: string }) => api.approve(id, b),
    onSettled: () => inv(),
  });
}
export function useRejectApproval(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (b: { note?: string }) => api.reject(id, b),
    onSuccess: () => inv(),
  });
}
export function useRetryApproval(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: () => api.retryApproval(id),
    onSettled: () => inv(),
  });
}
const BILLER_KEYS = ["billers", "beneficiaries", ...PAYMENT_KEYS];
export function useCreateBiller() {
  const inv = useInvalidate(BILLER_KEYS);
  return useMutation({
    mutationFn: (b: CreateBillerBody) => api.createBiller(b),
    onSuccess: () => inv(),
  });
}
export function useUpdateBiller() {
  const inv = useInvalidate(BILLER_KEYS);
  return useMutation({
    mutationFn: (v: { id: string; body: UpdateBillerBody }) => api.updateBiller(v.id, v.body),
    onSuccess: () => inv(),
  });
}
export function useSuspendBiller() {
  const inv = useInvalidate(BILLER_KEYS);
  return useMutation({ mutationFn: (id: string) => api.suspendBiller(id), onSuccess: () => inv() });
}
export function useReactivateBiller() {
  const inv = useInvalidate(BILLER_KEYS);
  return useMutation({
    mutationFn: (id: string) => api.reactivateBiller(id),
    onSuccess: () => inv(),
  });
}
export function useCreateBeneficiary() {
  const inv = useInvalidate(BILLER_KEYS);
  return useMutation({
    mutationFn: (b: CreateBeneficiaryBody) => api.createBeneficiary(b),
    onSuccess: () => inv(),
  });
}
export function useRevokeBeneficiary() {
  const inv = useInvalidate(BILLER_KEYS);
  return useMutation({
    mutationFn: (id: string) => api.revokeBeneficiary(id),
    onSuccess: () => inv(),
  });
}
export function useWitnessVerify() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (attemptId: string) => api.witnessVerify(attemptId),
    onSuccess: () => inv(),
  });
}
export function useUpdatePolicy() {
  const inv = useInvalidate(["policy", "dashboard"]);
  return useMutation({
    mutationFn: (b: UpdatePolicyBody) => api.updatePolicy(b),
    onSuccess: () => inv(),
  });
}
