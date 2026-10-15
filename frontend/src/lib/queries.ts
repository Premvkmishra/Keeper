import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "./api";
import type {
  ApprovalInvalidationReason,
  ApprovalStatus,
  ApproveBody,
  AttemptStatus,
  Bill,
  Biller,
  BillerCategory,
  BillerStatus,
  BillStatus,
  CreateBeneficiaryBody,
  CreateBillerBody,
  CreateBillBody,
  PayBillBody,
  RejectBody,
  SecurityEventType,
  Severity,
  UpdateBillerBody,
  UpdateBillBody,
  UpdatePolicyBody,
} from "./types";

export const PAGE_SIZE = 20;

export const qk = {
  me: ["me"] as const,
  health: ["health"] as const,
  dashboard: ["dashboard"] as const,
  bills: (params?: Record<string, any>) => ["bills", params] as const,
  bill: (id: string) => ["bills", id] as const,
  approvals: (params?: Record<string, any>) => ["approvals", params] as const,
  approval: (id: string) => ["approvals", id] as const,
  billers: ["billers"] as const,
  beneficiaries: (billerId?: string) => ["beneficiaries", billerId] as const,
  policy: ["policy"] as const,
  payments: (params?: Record<string, any>) => ["payments", params] as const,
  payment: (id: string) => ["payments", id] as const,
  witnessReports: (params?: Record<string, any>) =>
    ["witness-reports", params] as const,
  witnessReport: (id?: string | null) => ["witness-reports", id] as const,
  securityEvents: (params?: Record<string, any>) =>
    ["security-events", params] as const,
};

export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn: api.health,
    refetchInterval: 30000,
  });
}

export function usePendingApprovalCount(enabled: boolean = true) {
  return useQuery({
    queryKey: qk.approvals({ status: "pending", limit: 1 }),
    queryFn: () => api.getApprovals({ status: "pending", limit: 1 }),
    enabled,
    refetchInterval: 15000,
  });
}

export function useDashboard() {
  return useQuery({
    queryKey: qk.dashboard,
    queryFn: api.dashboard,
  });
}

export function useBills(params?: {
  status?: BillStatus;
  biller_id?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: qk.bills(params),
    queryFn: () => api.getBills({ limit: PAGE_SIZE, ...params }),
  });
}

export function useBill(billId: string) {
  return useQuery({
    queryKey: qk.bill(billId),
    queryFn: () => api.getBill(billId),
    enabled: Boolean(billId),
  });
}

export function useCreateBill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateBillBody) => api.createBill(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bills"] });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
    },
  });
}

export function useUpdateBill(billId?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateBillBody }) =>
      api.updateBill(id, body),
    onSuccess: (_, vars) => {
      void qc.invalidateQueries({ queryKey: ["bills"] });
      void qc.invalidateQueries({ queryKey: qk.bill(vars.id) });
      if (billId) {
        void qc.invalidateQueries({ queryKey: qk.bill(billId) });
      }
      void qc.invalidateQueries({ queryKey: qk.dashboard });
    },
  });
}

export function useCancelBill(billId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.cancelBill(billId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bills"] });
      void qc.invalidateQueries({ queryKey: qk.bill(billId) });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
    },
  });
}

export function usePayBill(billId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PayBillBody) => api.payBill(billId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["bills"] });
      void qc.invalidateQueries({ queryKey: qk.bill(billId) });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: ["approvals"] });
      void qc.invalidateQueries({ queryKey: ["payments"] });
    },
  });
}

export function useApprovals(params?: {
  status?: ApprovalStatus;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: qk.approvals(params),
    queryFn: () => api.getApprovals({ limit: PAGE_SIZE, ...params }),
  });
}

export function useApproval(approvalId: string) {
  return useQuery({
    queryKey: qk.approval(approvalId),
    queryFn: () => api.getApproval(approvalId),
    enabled: Boolean(approvalId),
  });
}

export function useApproveApproval(approvalId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ApproveBody) => api.approveApproval(approvalId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["approvals"] });
      void qc.invalidateQueries({ queryKey: qk.approval(approvalId) });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: ["bills"] });
      void qc.invalidateQueries({ queryKey: ["payments"] });
    },
  });
}

export function useRejectApproval(approvalId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RejectBody) => api.rejectApproval(approvalId, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["approvals"] });
      void qc.invalidateQueries({ queryKey: qk.approval(approvalId) });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: ["bills"] });
    },
  });
}

export function useRetryApproval(approvalId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.retryApproval(approvalId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["approvals"] });
      void qc.invalidateQueries({ queryKey: qk.approval(approvalId) });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
      void qc.invalidateQueries({ queryKey: ["bills"] });
      void qc.invalidateQueries({ queryKey: ["payments"] });
    },
  });
}

export function useBillers() {
  return useQuery({
    queryKey: qk.billers,
    queryFn: api.getBillers,
  });
}

export function useCreateBiller() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateBillerBody) => api.createBiller(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.billers });
    },
  });
}

export function useUpdateBiller() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateBillerBody }) =>
      api.updateBiller(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.billers });
    },
  });
}

export function useSuspendBiller() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (billerId: string) => api.suspendBiller(billerId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.billers });
    },
  });
}

export function useReactivateBiller() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (billerId: string) => api.reactivateBiller(billerId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.billers });
    },
  });
}

export function useBeneficiaries(billerId?: string) {
  return useQuery({
    queryKey: qk.beneficiaries(billerId),
    queryFn: () => api.getBeneficiaries(billerId),
  });
}

export function useCreateBeneficiary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateBeneficiaryBody) => api.createBeneficiary(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["beneficiaries"] });
      void qc.invalidateQueries({ queryKey: qk.billers });
    },
  });
}

export function useRevokeBeneficiary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.revokeBeneficiary(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["beneficiaries"] });
      void qc.invalidateQueries({ queryKey: qk.billers });
    },
  });
}

export function usePolicy() {
  return useQuery({
    queryKey: qk.policy,
    queryFn: api.getPolicy,
  });
}

export function useUpdatePolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdatePolicyBody) => api.updatePolicy(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.policy });
      void qc.invalidateQueries({ queryKey: qk.dashboard });
    },
  });
}

export function usePayments(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: qk.payments(params),
    queryFn: () => api.getPayments({ limit: PAGE_SIZE, ...params }),
  });
}

export function usePayment(attemptId: string) {
  return useQuery({
    queryKey: qk.payment(attemptId),
    queryFn: () => api.getPayment(attemptId),
    enabled: Boolean(attemptId),
  });
}

export function useWitnessReports(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: qk.witnessReports(params),
    queryFn: () => api.getWitnessReports({ limit: PAGE_SIZE, ...params }),
  });
}

export function useWitnessReport(
  reportId?: string | null,
  enabled: boolean = true,
) {
  return useQuery({
    queryKey: qk.witnessReport(reportId),
    queryFn: () => api.getWitnessReport(reportId!),
    enabled: Boolean(reportId && enabled),
  });
}

export function useWitnessVerify() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { attempt_id?: string; bill_id?: string }) =>
      api.verifyWitness(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["witness-reports"] });
      void qc.invalidateQueries({ queryKey: ["payments"] });
      void qc.invalidateQueries({ queryKey: ["bills"] });
    },
  });
}

export function useSecurityEvents(params?: {
  severity?: Severity;
  event_type?: SecurityEventType;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: qk.securityEvents(params),
    queryFn: () => api.getSecurityEvents({ limit: PAGE_SIZE, ...params }),
  });
}
