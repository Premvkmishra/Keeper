import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { formatMoney, normalizeMoney, validateMoney } from "@/lib/money";
import { ApiError, parseApiError } from "@/lib/api";
import * as F from "@/lib/format";
import { OutcomePanel } from "@/components/outcome/OutcomePanel";
import { ApproveDialog } from "@/components/ApproveDialog";
import { approvalFixture, highValueOutcome, maliciousOutcome, normalOutcome } from "./fixtures";

describe("money", () => {
  it("formats INR from strings", () => {
    expect(formatMoney("2400.00")).toBe("₹2,400.00");
    expect(formatMoney("48000.00")).toBe("₹48,000.00");
  });
  it("normalizes to two-decimal strings", () => {
    expect(normalizeMoney("2400")).toBe("2400.00");
    expect(normalizeMoney("2400.5")).toBe("2400.50");
    expect(normalizeMoney("1.234")).toBeNull();
  });
  it("enforces bill limits", () => {
    expect(validateMoney("0", { min: "0.00", max: "10000000.00", positive: true })).not.toBeNull();
    expect(
      validateMoney("10000000.01", { min: "0.00", max: "10000000.00", positive: true }),
    ).not.toBeNull();
    expect(
      validateMoney("10000000.00", { min: "0.00", max: "10000000.00", positive: true }),
    ).toBeNull();
  });
});

describe("ApiError parsing", () => {
  it("parses the error envelope", () => {
    const e = parseApiError(409, {
      error: { code: "approval_expired", message: "Expired", details: { a: 1 }, request_id: "r1" },
    });
    expect(e).toBeInstanceOf(ApiError);
    expect(e.code).toBe("approval_expired");
    expect(e.request_id).toBe("r1");
    expect(e.status).toBe(409);
  });
  it("exposes validation field errors", () => {
    const e = parseApiError(422, {
      error: {
        code: "validation_error",
        message: "Bad",
        details: { fields: { title: "Required" } },
        request_id: "r",
      },
    });
    expect(e.fieldErrors).toEqual({ title: "Required" });
  });
});

describe("status labels cover every enum value", () => {
  it("bill_status", () => {
    expect(Object.keys(F.BILL_STATUS).sort()).toEqual([
      "awaiting_approval",
      "blocked",
      "cancelled",
      "failed",
      "needs_review",
      "paid",
      "processing",
      "received",
    ]);
    expect(F.BILL_STATUS.received.label).toBe("Ready to pay");
  });
  it("attempt_status", () => expect(Object.keys(F.ATTEMPT_STATUS)).toHaveLength(5));
  it("decision", () => expect(F.DECISION.require_approval.label).toBe("Needs a person"));
  it("approval_status", () => expect(Object.keys(F.APPROVAL_STATUS)).toHaveLength(6));
  it("witness_verdict", () => expect(Object.keys(F.WITNESS_VERDICT)).toHaveLength(4));
  it("severity", () => expect(Object.keys(F.SEVERITY)).toHaveLength(3));
  it("reason_code", () => {
    expect(Object.keys(F.REASON_CODE)).toHaveLength(15);
    expect(F.REASON_CODE.beneficiary_not_approved).toBe(
      "Payee account is not on your approved list",
    );
  });
  it("others", () => {
    expect(Object.keys(F.MEMBER_ROLE)).toHaveLength(3);
    expect(Object.keys(F.BILLER_CATEGORY)).toHaveLength(7);
    expect(F.BILLER_STATUS.suspended.label).toBe("Paused");
    expect(F.BENEFICIARY_STATUS.revoked.label).toBe("Removed");
    expect(F.SECURITY_EVENT_TYPES).toHaveLength(26);
    expect(F.eventTypeLabel("beneficiary_mismatch")).toBe("Beneficiary mismatch");
  });
});

describe("OutcomePanel", () => {
  it("normal payment shows allowed, processed, witness found", () => {
    render(<OutcomePanel outcome={normalOutcome} showBillLink={false} />);
    expect(screen.getByText("1. Authorization")).toBeInTheDocument();
    expect(screen.getByText("Allowed")).toBeInTheDocument();
    expect(screen.getByText("Bank processed it")).toBeInTheDocument();
    expect(screen.getByText("Witness confirms: payment found in bank ledger")).toBeInTheDocument();
  });
  it("malicious beneficiary shows denied and no payment", () => {
    render(<OutcomePanel outcome={maliciousOutcome} showBillLink={false} />);
    expect(screen.getByText("Denied")).toBeInTheDocument();
    expect(screen.getByText("No payment was sent to the bank.")).toBeInTheDocument();
    expect(screen.getByText("Witness confirms: no payment in bank ledger")).toBeInTheDocument();
  });
  it("high value shows needs a person and waiting", () => {
    render(<OutcomePanel outcome={highValueOutcome} showBillLink={false} />);
    expect(screen.getByText("Needs a person")).toBeInTheDocument();
    expect(screen.getByText("Waiting for approval")).toBeInTheDocument();
    expect(screen.getByText(/Nothing has been sent to the bank/)).toBeInTheDocument();
  });
});

describe("ApproveDialog gating", () => {
  it("confirm is disabled until the checkbox is ticked", () => {
    const onConfirm = vi.fn();
    render(
      <ApproveDialog
        approval={approvalFixture}
        open
        onOpenChange={() => {}}
        pending={false}
        onConfirm={onConfirm}
      />,
    );
    const btn = screen.getByRole("button", { name: /Approve and pay ₹48,000.00/ });
    expect(btn).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    expect(btn).toBeEnabled();
    fireEvent.click(btn);
    expect(onConfirm).toHaveBeenCalled();
  });
});
