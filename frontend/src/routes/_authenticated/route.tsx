import { useEffect } from "react";
import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AppShell, DemoBadge } from "@/components/layout/AppShell";
import { ErrorAlert } from "@/components/common";
import { api, ApiError, onUnauthorized } from "@/lib/api";
import { MeProvider } from "@/lib/auth";
import { qk } from "@/lib/queries";
import { getAuthClient, isAuthConfigured, isDevAuth, isSupabaseConfigured } from "@/lib/supabase";

export const Route = createFileRoute("/_authenticated")({
  ssr: false,
  beforeLoad: async () => {
    if (isDevAuth()) return;
    if (!isAuthConfigured()) throw redirect({ to: "/login" });
    const { data } = await getAuthClient().auth.getSession();
    if (!data.session) throw redirect({ to: "/login" });
  },
  component: AuthedLayout,
});

async function signOutToLogin(qc: ReturnType<typeof useQueryClient>) {
  await qc.cancelQueries();
  qc.clear();
  localStorage.removeItem("keeper_dev_token");
  if (isSupabaseConfigured()) {
    try {
      await getAuthClient().auth.signOut();
    } catch {
      // ignore
    }
  }
  window.location.replace("/login");
}

function AuthedLayout() {
  const qc = useQueryClient();
  const me = useQuery({ queryKey: qk.me, queryFn: api.me, retry: false });

  useEffect(() => {
    onUnauthorized(() => void signOutToLogin(qc));
    if (!isSupabaseConfigured()) return;
    const { data } = getAuthClient().auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") window.location.replace("/login");
    });
    return () => data.subscription.unsubscribe();
  }, [qc]);

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
                You're signed in, but your account isn't part of a household yet. The person who
                runs Keeper's setup needs to create your household and add you to it. You can't do
                this from here.
              </p>
              <p className="mt-3 text-muted-foreground">
                Once they tell you it's done, press "Check again".
              </p>
            </>
          ) : (
            <ErrorAlert error={me.error} />
          )}
          <div className="mt-6 flex flex-wrap gap-3">
            <Button onClick={() => me.refetch()} disabled={me.isFetching}>
              {me.isFetching ? "Checking…" : "Check again"}
            </Button>
            <Button variant="outline" onClick={() => void signOutToLogin(qc)}>
              Sign out
            </Button>
          </div>
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
