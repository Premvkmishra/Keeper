import { describe, expect, it, beforeEach } from "vitest";
import { getAuthToken, setAuthToken, clearAuthToken, isDevAuth } from "@/lib/supabase";
import { ApiError, parseApiError } from "@/lib/api";

describe("Frontend Authentication State", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it("stores and retrieves auth token correctly", () => {
    expect(getAuthToken()).toBeNull();
    expect(isDevAuth()).toBe(false);

    setAuthToken("test-jwt-token-123");
    expect(getAuthToken()).toBe("test-jwt-token-123");
    expect(isDevAuth()).toBe(true);

    clearAuthToken();
    expect(getAuthToken()).toBeNull();
    expect(isDevAuth()).toBe(false);
  });

  it("parses 401 unauthenticated error correctly", () => {
    const err = parseApiError(401, {
      error: {
        code: "unauthenticated",
        message: "Invalid email or password.",
        details: {},
        request_id: "req-123",
      },
    });

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(err.code).toBe("unauthenticated");
    expect(err.message).toBe("Invalid email or password.");
  });

  it("parses 409 duplicate registration error with field details", () => {
    const err = parseApiError(409, {
      error: {
        code: "duplicate_resource",
        message: "An account with this email address already exists.",
        details: { fields: { email: "An account with this email already exists." } },
        request_id: "req-456",
      },
    });

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.fieldErrors?.email).toBe("An account with this email already exists.");
  });
});
