import { useState, type FormEvent } from "react";
import { createFileRoute, useRouter } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ensureHouseholdForCurrentUser } from "@/lib/onboarding";
import { getAuthClient, isSupabaseConfigured } from "@/lib/supabase";

export const Route = createFileRoute("/login")({
  ssr: false,
  component: LoginPage,
});

export function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [householdName, setHouseholdName] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const authConfigured = isSupabaseConfigured();

  async function continueToKeeper(profile?: { displayName?: string; householdName?: string }) {
    await ensureHouseholdForCurrentUser(profile);
    await router.navigate({ to: "/" });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setSubmitting(true);

    try {
      if (!authConfigured) {
        throw new Error(
          "Sign-in is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in frontend/.env.",
        );
      }

      const auth = getAuthClient().auth;
      if (mode === "login") {
        const { error: authError } = await auth.signInWithPassword({
          email: email.trim(),
          password,
        });
        if (authError) throw authError;
        await continueToKeeper();
        return;
      }

      const { data, error: authError } = await auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: {
            display_name: displayName.trim(),
            household_name: householdName.trim(),
          },
        },
      });
      if (authError) throw authError;

      if (data.session) {
        await continueToKeeper({
          displayName: displayName.trim(),
          householdName: householdName.trim(),
        });
      } else {
        setMode("login");
        setNotice("Account created. Check your email to confirm it, then sign in to continue.");
      }
    } catch (cause) {
      const authError =
        cause instanceof Error ? (cause as Error & { status?: number; code?: string }) : null;
      if (
        authError?.status === 429 ||
        authError?.code === "over_email_send_rate_limit" ||
        authError?.message.toLowerCase().includes("email rate limit exceeded")
      ) {
        setError(
          "Supabase has temporarily rate-limited confirmation emails. Wait before retrying. To send signup emails to Gmail and other addresses reliably, configure custom SMTP in Supabase Auth; its built-in email service is limited to 2 emails per hour.",
        );
      } else {
        setError(
          cause instanceof Error ? cause.message : "Unable to complete sign-in. Please retry.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  function changeMode(nextMode: "login" | "signup") {
    setMode(nextMode);
    setError("");
    setNotice("");
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border bg-card p-6 shadow-sm sm:p-8">
        <div className="mb-7 text-center">
          <p className="text-3xl font-bold text-primary">Keeper</p>
          <p className="mt-2 text-muted-foreground">
            Safe bill payments, with a person in control.
          </p>
        </div>

        <div
          className="mb-6 grid grid-cols-2 gap-2 rounded-xl bg-muted p-1"
          role="tablist"
          aria-label="Account"
        >
          <button
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            className={`min-h-11 rounded-lg px-3 font-bold ${mode === "login" ? "bg-card text-primary shadow-sm" : "text-muted-foreground"}`}
            onClick={() => changeMode("login")}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "signup"}
            className={`min-h-11 rounded-lg px-3 font-bold ${mode === "signup" ? "bg-card text-primary shadow-sm" : "text-muted-foreground"}`}
            onClick={() => changeMode("signup")}
          >
            Sign up
          </button>
        </div>

        <h1 className="text-2xl font-bold">
          {mode === "login" ? "Welcome back" : "Create your Keeper account"}
        </h1>
        <p className="mt-2 text-muted-foreground">
          {mode === "login"
            ? "Sign in with your email and password."
            : "Your new account starts a private household that you manage."}
        </p>

        <form className="mt-6 space-y-4" onSubmit={(event) => void submit(event)}>
          {mode === "signup" ? (
            <>
              <div className="space-y-2">
                <Label htmlFor="display-name">Your name</Label>
                <Input
                  id="display-name"
                  autoComplete="name"
                  required
                  maxLength={255}
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="household-name">Household name</Label>
                <Input
                  id="household-name"
                  autoComplete="organization"
                  required
                  maxLength={255}
                  value={householdName}
                  onChange={(event) => setHouseholdName(event.target.value)}
                />
              </div>
            </>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              maxLength={255}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={mode === "signup" ? 8 : undefined}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            {mode === "signup" ? (
              <p className="text-sm text-muted-foreground">Use at least 8 characters.</p>
            ) : null}
          </div>

          {error ? (
            <p role="alert" className="rounded-lg bg-danger-bg p-3 text-sm text-danger">
              {error}
            </p>
          ) : null}
          {notice ? (
            <p role="status" className="rounded-lg bg-info-bg p-3 text-sm text-info">
              {notice}
            </p>
          ) : null}

          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
          {!authConfigured ? (
            <p className="text-sm text-warning" role="status">
              Authentication needs Supabase configuration before sign-in or sign-up can work.
            </p>
          ) : null}
        </form>
      </section>
    </main>
  );
}
