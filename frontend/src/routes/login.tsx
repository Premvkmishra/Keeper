import { useState, type FormEvent, type ReactNode } from "react";
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FieldError, SubmitLabel } from "@/components/common";
import { DemoBadge } from "@/components/layout/AppShell";
import {
  DEV_TOKEN,
  getAuthClient,
  isAuthConfigured,
  isDevAuth,
  isSupabaseConfigured,
} from "@/lib/supabase";

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
    if (isDevAuth()) throw redirect({ to: "/" });
    if (!isSupabaseConfigured()) return;
    const { data } = await getAuthClient().auth.getSession();
    if (data.session) throw redirect({ to: "/" });
  },
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (!isSupabaseConfigured()) {
    return (
      <Shell>
        <div
          role="alert"
          className="rounded-lg border border-warning/40 bg-warning-bg p-4 text-warning"
        >
          <p className="font-bold">Supabase Cloud sign-in is not configured.</p>
          <p className="mt-1">
            To connect live Supabase, set <code>VITE_SUPABASE_ANON_KEY</code> in{" "}
            <code>frontend/.env</code>.
          </p>
        </div>
        <div className="mt-6 border-t pt-6">
          <p className="mb-3 text-sm text-muted-foreground">
            Or test locally right now with the pre-seeded owner account:
          </p>
          <Button
            type="button"
            className="w-full h-12 text-base font-bold"
            onClick={async () => {
              localStorage.setItem("keeper_dev_token", DEV_TOKEN);
              await navigate({ to: "/", replace: true });
            }}
          >
            Sign in with Local Dev Account (u1@test.com)
          </Button>
        </div>
      </Shell>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (pending) return;
    setError(null);
    setNotice(null);
    if (!email.trim()) return setError("Please enter your email.");
    if (mode === "signup" && password.length < 8)
      return setError("Your password needs at least 8 characters.");
    if (!password) return setError("Please enter your password.");
    setPending(true);
    try {
      const auth = getAuthClient().auth;
      if (mode === "signin") {
        const { error } = await auth.signInWithPassword({ email: email.trim(), password });
        if (error) throw error;
        await navigate({ to: "/", replace: true });
      } else {
        const { data, error } = await auth.signUp({
          email: email.trim(),
          password,
          options: { emailRedirectTo: window.location.origin },
        });
        if (error) throw error;
        if (data.session) await navigate({ to: "/", replace: true });
        else setNotice("Account created. Please check your email to confirm, then sign in.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't sign you in. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Shell>
      <h1 className="mb-1">{mode === "signin" ? "Sign in to Keeper" : "Create your account"}</h1>
      <p className="mb-6 text-muted-foreground">Keeper helps you pay bills safely.</p>
      <form onSubmit={submit} noValidate className="space-y-4">
        <div>
          <Label htmlFor="email" className="text-base font-bold">
            Email
          </Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 h-12 text-base"
            aria-describedby={error ? "login-error" : undefined}
          />
        </div>
        <div>
          <Label htmlFor="password" className="text-base font-bold">
            Password
          </Label>
          <Input
            id="password"
            type="password"
            autoComplete={mode === "signin" ? "current-password" : "new-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 h-12 text-base"
            aria-describedby={mode === "signup" ? "pw-hint" : undefined}
          />
          {mode === "signup" && (
            <p id="pw-hint" className="mt-1 text-muted-foreground">
              At least 8 characters.
            </p>
          )}
        </div>
        <div aria-live="polite">
          <FieldError id="login-error" msg={error ?? undefined} />
          {notice && (
            <p className="rounded-md bg-success-bg p-3 font-bold text-success">{notice}</p>
          )}
        </div>
        <Button type="submit" className="w-full" disabled={pending}>
          <SubmitLabel
            pending={pending}
            idle={mode === "signin" ? "Sign in" : "Create account"}
            busy={mode === "signin" ? "Signing in…" : "Creating…"}
          />
        </Button>
      </form>
      <Button
        variant="link"
        className="mt-4 px-0"
        onClick={() => {
          setMode(mode === "signin" ? "signup" : "signin");
          setError(null);
          setNotice(null);
        }}
      >
        {mode === "signin" ? "Create account" : "I already have an account — sign in"}
      </Button>
      <div className="mt-6 border-t pt-4 space-y-3">
        <p className="mb-2 text-xs text-muted-foreground text-center">
          Local Development Shortcut:
        </p>
        <Button
          type="button"
          variant="outline"
          className="w-full h-11 text-sm font-semibold"
          onClick={async () => {
            localStorage.setItem("keeper_dev_token", DEV_TOKEN);
            await navigate({ to: "/", replace: true });
          }}
        >
          Sign in with Local Dev Account (u1@test.com)
        </Button>
        <Button
          type="button"
          variant="default"
          className="w-full h-11 text-sm font-semibold"
          onClick={async () => {
            setPending(true);
            setError(null);
            try {
              const response = await fetch(`${import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}/api/v1/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username: "admin", password: "admin" }),
              });

              const json = (await response.json().catch(() => null)) as
                | { token?: string; error?: { message?: string } }
                | null;

              if (!response.ok || !json?.token) {
                throw new Error(json?.error?.message ?? "Admin login failed.");
              }

              localStorage.setItem("keeper_dev_token", json.token);
              await navigate({ to: "/", replace: true });
            } catch (err) {
              setError(err instanceof Error ? err.message : "Admin login failed.");
            } finally {
              setPending(false);
            }
          }}
        >
          Sign in as admin (admin / admin)
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
      <div className="w-full max-w-md rounded-lg border bg-card p-6">{children}</div>
      <p className="mt-6 text-muted-foreground">Keeper never moves real money in this demo.</p>
    </main>
  );
}
