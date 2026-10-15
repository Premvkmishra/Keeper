import { useState, type FormEvent, type ReactNode } from "react";
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FieldError, SubmitLabel } from "@/components/common";
import { DemoBadge } from "@/components/layout/AppShell";
import { api, ApiError, friendlyErrorMessage } from "@/lib/api";
import { getAuthToken, setAuthToken } from "@/lib/supabase";

export const Route = createFileRoute("/login")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Sign in — Keeper" },
      {
        name: "description",
        content: "Sign in to Keeper to review bills, approvals and safety checks.",
      },
      { property: "og:title", content: "Sign in — Keeper" },
      {
        property: "og:description",
        content: "Sign in to Keeper to review bills, approvals and safety checks.",
      },
    ],
  }),
  beforeLoad: async () => {
    if (getAuthToken()) throw redirect({ to: "/" });
  },
  component: LoginPage,
});

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  function validate(): boolean {
    const errs: Record<string, string> = {};
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      errs.email = "Please enter your email address.";
    } else if (!EMAIL_REGEX.test(trimmedEmail)) {
      errs.email = "Please enter a valid email address.";
    }

    if (!password) {
      errs.password = "Please enter your password.";
    } else if (password.length < 8) {
      errs.password = "Password must be at least 8 characters.";
    }

    if (mode === "signup") {
      if (!displayName.trim()) {
        errs.displayName = "Please enter your display name.";
      }
      if (!confirmPassword) {
        errs.confirmPassword = "Please confirm your password.";
      } else if (password !== confirmPassword) {
        errs.confirmPassword = "Passwords do not match.";
      }
    }

    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    setError(null);
    setNotice(null);

    if (!validate()) return;

    setPending(true);
    try {
      if (mode === "signin") {
        const res = await api.login({
          email: email.trim().toLowerCase(),
          password,
        });
        setAuthToken(res.token);
        await navigate({ to: "/", replace: true });
      } else {
        const res = await api.register({
          display_name: displayName.trim(),
          email: email.trim().toLowerCase(),
          password,
          confirm_password: confirmPassword,
        });
        setAuthToken(res.token);
        await navigate({ to: "/", replace: true });
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.fieldErrors) {
          setFieldErrors((prev) => ({ ...prev, ...err.fieldErrors }));
        }
        setError(err.message);
      } else if (
        err instanceof TypeError ||
        (err instanceof Error && err.message.includes("Failed to fetch"))
      ) {
        setError(
          "Unable to connect to Keeper server. Please ensure the backend is running at http://localhost:8000.",
        );
      } else {
        setError(friendlyErrorMessage(err));
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <Shell>
      <h1 className="mb-1 text-2xl font-bold text-foreground">
        {mode === "signin" ? "Sign in to Keeper" : "Create your account"}
      </h1>
      <p className="mb-6 text-muted-foreground">Keeper helps you pay bills safely.</p>

      <form onSubmit={submit} noValidate className="space-y-4">
        {mode === "signup" && (
          <div>
            <Label htmlFor="displayName" className="text-sm font-semibold">
              Full Name / Display Name
            </Label>
            <Input
              id="displayName"
              type="text"
              autoComplete="name"
              placeholder="e.g. John Doe"
              value={displayName}
              onChange={(e) => {
                setDisplayName(e.target.value);
                setFieldErrors((prev) => ({ ...prev, displayName: "" }));
              }}
              className="mt-1 h-11 text-base"
              aria-describedby={fieldErrors.displayName ? "displayName-error" : undefined}
            />
            <FieldError id="displayName-error" msg={fieldErrors.displayName} />
          </div>
        )}

        <div>
          <Label htmlFor="email" className="text-sm font-semibold">
            Email address
          </Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setFieldErrors((prev) => ({ ...prev, email: "" }));
            }}
            className="mt-1 h-11 text-base"
            aria-describedby={fieldErrors.email ? "email-error" : undefined}
          />
          <FieldError id="email-error" msg={fieldErrors.email} />
        </div>

        <div>
          <Label htmlFor="password" className="text-sm font-semibold">
            Password
          </Label>
          <Input
            id="password"
            type="password"
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            placeholder="••••••••"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setFieldErrors((prev) => ({ ...prev, password: "" }));
            }}
            className="mt-1 h-11 text-base"
            aria-describedby={
              fieldErrors.password
                ? "password-error"
                : mode === "signup"
                  ? "pw-hint"
                  : undefined
            }
          />
          {mode === "signup" && (
            <p id="pw-hint" className="mt-1 text-xs text-muted-foreground">
              At least 8 characters.
            </p>
          )}
          <FieldError id="password-error" msg={fieldErrors.password} />
        </div>

        {mode === "signup" && (
          <div>
            <Label htmlFor="confirmPassword" className="text-sm font-semibold">
              Confirm password
            </Label>
            <Input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                setFieldErrors((prev) => ({ ...prev, confirmPassword: "" }));
              }}
              className="mt-1 h-11 text-base"
              aria-describedby={
                fieldErrors.confirmPassword ? "confirmPassword-error" : undefined
              }
            />
            <FieldError id="confirmPassword-error" msg={fieldErrors.confirmPassword} />
          </div>
        )}

        <div aria-live="polite">
          {error && <FieldError id="login-error" msg={error} />}
          {notice && (
            <p className="rounded-md bg-success-bg p-3 font-semibold text-success">{notice}</p>
          )}
        </div>

        <Button type="submit" className="w-full h-11 text-base font-semibold" disabled={pending}>
          <SubmitLabel
            pending={pending}
            idle={mode === "signin" ? "Sign in" : "Create account"}
            busy={mode === "signin" ? "Signing in…" : "Creating account…"}
          />
        </Button>
      </form>

      <div className="mt-4 text-center">
        <Button
          variant="link"
          className="px-0 text-sm font-medium"
          onClick={() => {
            setMode(mode === "signin" ? "signup" : "signin");
            setError(null);
            setFieldErrors({});
            setNotice(null);
          }}
        >
          {mode === "signin"
            ? "Don't have an account? Create one"
            : "Already have an account? Sign in"}
        </Button>
      </div>

      <div className="mt-6 border-t pt-4">
        <p className="mb-2 text-xs text-muted-foreground text-center">
          Quick Demo Credentials:
        </p>
        <Button
          type="button"
          variant="outline"
          className="w-full h-10 text-xs font-medium"
          disabled={pending}
          onClick={async () => {
            setEmail("admin@keeper.local");
            setPassword("admin");
            setError(null);
            setFieldErrors({});
            setPending(true);
            try {
              const res = await api.login({
                email: "admin@keeper.local",
                password: "admin",
              });
              setAuthToken(res.token);
              await navigate({ to: "/", replace: true });
            } catch (err) {
              setError(friendlyErrorMessage(err));
            } finally {
              setPending(false);
            }
          }}
        >
          Sign in as Demo Admin (admin@keeper.local / admin)
        </Button>
      </div>
    </Shell>
  );
}

function Shell({ children }: { children: ReactNode }) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <div className="mb-6 flex flex-col items-center gap-3">
        <span className="text-4xl font-bold text-primary">Keeper</span>
        <DemoBadge />
      </div>
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-sm">{children}</div>
      <p className="mt-6 text-sm text-muted-foreground">
        Keeper never moves real money in this simulated environment.
      </p>
    </main>
  );
}
