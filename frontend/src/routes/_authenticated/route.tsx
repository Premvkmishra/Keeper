import { useEffect, useState } from "react";
import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AppShell, DemoBadge } from "@/components/layout/AppShell";
import { ErrorAlert } from "@/components/common";
import { api, ApiError, onUnauthorized } from "@/lib/api";
import { MeProvider } from "@/lib/auth";
import { ensureHouseholdForCurrentUser } from "@/lib/onboarding";
import { qk } from "@/lib/queries";
import { getAuthClient, isSupabaseConfigured } from "@/lib/supabase";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async () => {
    if (!isSupabaseConfigured()) throw redirect({ to: "/login" });
    const { data } = await getAuthClient().auth.getSession();
    if (!data.session) throw redirect({ to: "/login" });
  },
  component: AuthedLayout,
});

async function stayInApp(qc: ReturnType<typeof useQueryClient>) {
  await qc.cancelQueries();
  qc.clear();
  if (isSupabaseConfigured()) await getAuthClient().auth.signOut({ scope: "local" });
  window.location.replace("/login");
}

function AuthedLayout() {
  const qc = useQueryClient();
  const me = useQuery({ queryKey: qk.me, queryFn: api.me, retry: false });
  const [setupPending, setSetupPending] = useState(false);
  const [setupError, setSetupError] = useState("");

  useEffect(() => {
    onUnauthorized(() => void stayInApp(qc));
    if (!isSupabaseConfigured()) return;
    const { data } = getAuthClient().auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") window.location.replace("/login");
    });
    return () => data.subscription.unsubscribe();
  }, [qc]);

  async function setupHousehold() {
    setSetupPending(true);
    setSetupError("");
    try {
      await ensureHouseholdForCurrentUser();
      await me.refetch();
    } catch (cause) {
      setSetupError(
        cause instanceof Error ? cause.message : "Household setup failed. Please retry.",
      );
    } finally {
      setSetupPending(false);
    }
  }

  if (me.isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-3" role="status">
        <Loader2 aria-hidden className="size-6 animate-spin text-primary" />
        <span>Loading your household…</span>
      </div>
    );
  }

  if (me.error) {
    const noHousehold =
      me.error instanceof ApiError &&
      me.error.status === 403 &&
      me.error.details["reason"] === "no_household_membership";
    return (
      <main className="flex min-h-screen flex-col items-center justify-center px-4">
        <div className="mb-6 flex flex-col items-center gap-3">
          <span className="text-4xl font-bold text-primary">Keeper</span>
          <DemoBadge />
        </div>
        <div className="w-full max-w-lg rounded-lg border bg-card p-6">
          {noHousehold ? (
            <>
              <h1>Account not set up yet</h1>
              <p className="mt-3">
                Finish setting up your private Keeper household to start using the app.
              </p>
              {setupError ? (
                <p role="alert" className="mt-3 text-danger">
                  {setupError}
                </p>
              ) : null}
              <Button
                className="mt-4"
                onClick={() => void setupHousehold()}
                disabled={setupPending}
              >
                {setupPending ? "Setting up…" : "Set up my household"}
              </Button>
            </>
          ) : (
            <ErrorAlert error={me.error} />
          )}
          {!noHousehold ? (
            <div className="mt-6 flex flex-wrap gap-3">
              <Button onClick={() => me.refetch()} disabled={me.isFetching}>
                {me.isFetching ? "Checking…" : "Check again"}
              </Button>
              <Button variant="outline" onClick={() => void stayInApp(qc)}>
                Sign out
              </Button>
            </div>
          ) : null}
        </div>
      </main>
    );
  }

  if (!me.data) return null;
  return (
    <MeProvider me={me.data}>
      <AppShell>
        <Outlet />
      </AppShell>
    </MeProvider>
  );
}
