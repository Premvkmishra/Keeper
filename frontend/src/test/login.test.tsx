import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "@/routes/login";

const authMocks = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  navigate: vi.fn(),
  ensureHousehold: vi.fn(),
}));

vi.mock("@tanstack/react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-router")>();
  return { ...actual, useRouter: () => ({ navigate: authMocks.navigate }) };
});

vi.mock("@/lib/supabase", () => ({
  getAuthClient: () => ({
    auth: {
      signInWithPassword: authMocks.signInWithPassword,
      signUp: authMocks.signUp,
    },
  }),
  isSupabaseConfigured: () => true,
}));

vi.mock("@/lib/onboarding", () => ({
  ensureHouseholdForCurrentUser: authMocks.ensureHousehold,
}));

describe("login and signup", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMocks.signInWithPassword.mockResolvedValue({ error: null });
    authMocks.signUp.mockResolvedValue({ data: { session: {} }, error: null });
    authMocks.ensureHousehold.mockResolvedValue(undefined);
    authMocks.navigate.mockResolvedValue(undefined);
  });

  it("signs in then provisions the account household before opening the app", async () => {
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "owner@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "passphrase" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(authMocks.navigate).toHaveBeenCalledWith({ to: "/" }));
    expect(authMocks.signInWithPassword).toHaveBeenCalledWith({
      email: "owner@example.test",
      password: "passphrase",
    });
    expect(authMocks.ensureHousehold).toHaveBeenCalledWith(undefined);
  });

  it.each(["new@example.test", "new.user@gmail.com"])(
    "creates a Supabase account for %s, creates its household and then enters Keeper",
    async (email) => {
      render(<LoginPage />);
      fireEvent.click(screen.getByRole("tab", { name: "Sign up" }));
      fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "New Owner" } });
      fireEvent.change(screen.getByLabelText("Household name"), {
        target: { value: "New Household" },
      });
      fireEvent.change(screen.getByLabelText("Email"), {
        target: { value: email },
      });
      fireEvent.change(screen.getByLabelText("Password"), {
        target: { value: "long-enough-password" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Create account" }));

      await waitFor(() => expect(authMocks.navigate).toHaveBeenCalledWith({ to: "/" }));
      expect(authMocks.signUp).toHaveBeenCalledWith({
        email,
        password: "long-enough-password",
        options: {
          data: { display_name: "New Owner", household_name: "New Household" },
        },
      });
      expect(authMocks.ensureHousehold).toHaveBeenCalledWith({
        displayName: "New Owner",
        householdName: "New Household",
      });
    },
  );

  it("explains how to recover from Supabase email rate limiting", async () => {
    authMocks.signUp.mockResolvedValueOnce({
      data: { session: null },
      error: Object.assign(new Error("email rate limit exceeded"), {
        status: 429,
        code: "over_email_send_rate_limit",
      }),
    });
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("tab", { name: "Sign up" }));
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "New Owner" } });
    fireEvent.change(screen.getByLabelText("Household name"), {
      target: { value: "New Household" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new.user@gmail.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "long-enough-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "temporarily rate-limited confirmation emails",
    );
    expect(screen.getByRole("alert")).toHaveTextContent("configure custom SMTP in Supabase Auth");
    expect(authMocks.navigate).not.toHaveBeenCalled();
  });

  it("shows the email-confirmation notice when Supabase requires verification", async () => {
    authMocks.signUp.mockResolvedValueOnce({ data: { session: null }, error: null });
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("tab", { name: "Sign up" }));
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "New Owner" } });
    fireEvent.change(screen.getByLabelText("Household name"), {
      target: { value: "New Household" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new@example.test" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "long-enough-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Check your email to confirm it, then sign in to continue.",
    );
    expect(authMocks.navigate).not.toHaveBeenCalled();
  });

});
