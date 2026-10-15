import { useEffect, useState, type ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { LogOut, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { useMe } from "@/lib/auth";
import { MEMBER_ROLE } from "@/lib/format";
import { useHealth, usePendingApprovalCount } from "@/lib/queries";
import { getAuthClient } from "@/lib/supabase";

type NavTo = "/" | "/bills" | "/approvals" | "/payments" | "/witness" | "/policy" | "/profile";

function useNavItems() {
  const pending = usePendingApprovalCount(true);
  return [
    { to: "/", label: "Home" },
    { to: "/bills", label: "Bills" },
    { to: "/approvals", label: "Approvals", badge: pending.data?.total },
    { to: "/payments", label: "Payment history" },
    { to: "/witness", label: "Witness" },
    { to: "/policy", label: "Safety limits" },
    { to: "/profile", label: "Profile" },
  ];
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const items = useNavItems();
  return (
    <nav aria-label="Main">
      <ul className="space-y-1">
        {items.map((i) => (
          <li key={i.to}>
            <Link
              to={i.to}
              onClick={onNavigate}
              activeOptions={{ exact: i.to === "/" }}
              className="flex min-h-12 items-center justify-between rounded-lg px-4 font-bold text-foreground hover:bg-accent"
              activeProps={{ className: "bg-accent text-primary", "aria-current": "page" }}
            >
              <span>{i.label}</span>
              {i.badge ? (
                <span
                  className="tabular rounded-full bg-warning-bg px-2.5 text-warning"
                  aria-label={`${i.badge} waiting`}
                >
                  {i.badge}
                </span>
              ) : null}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function HealthLine() {
  const h = useHealth();
  const ok = h.data?.status === "ok";
  return <span>Backend: {h.isLoading ? "checking…" : ok ? "connected" : "unavailable"}</span>;
}

export function DemoBadge() {
  return (
    <span className="inline-flex items-center rounded-full border border-warning/40 bg-warning-bg px-3 py-1 text-sm font-bold text-warning">
      Demo — simulated bank, no real money
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  useEffect(() => setOpen(false), [pathname]);

  async function signOut() {
    await qc.cancelQueries();
    qc.clear();
    await getAuthClient().auth.signOut();
    window.location.replace("/login");
  }

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-30 border-b bg-card">
        <div className="flex flex-wrap items-center gap-3 px-4 py-3 lg:pl-[284px]">
          <Button
            variant="outline"
            size="sm"
            className="lg:hidden"
            onClick={() => setOpen(true)}
            aria-expanded={open}
          >
            <Menu aria-hidden /> Menu
          </Button>
          <div className="lg:hidden">
            <span className="text-2xl font-bold text-primary">Keeper</span>
          </div>
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1">
            <span className="font-bold">{me.household.name}</span>
            <span className="text-muted-foreground">
              {me.display_name} · {MEMBER_ROLE[me.role]}
            </span>
            <DemoBadge />
          </div>
          <Button variant="outline" size="sm" onClick={signOut}>
            <LogOut aria-hidden /> Sign out
          </Button>
        </div>
      </header>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[260px] flex-col border-r bg-sidebar p-4 lg:flex">
        <Link to="/" className="mb-6 px-4 text-3xl font-bold text-primary">
          Keeper
        </Link>
        <NavList />
      </aside>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="left" className="w-[85vw] max-w-sm bg-sidebar p-4 [&>button]:hidden">
          <div className="mb-4 flex items-center justify-between">
            <SheetTitle className="text-2xl font-bold text-primary">Keeper</SheetTitle>
            <Button variant="outline" size="sm" onClick={() => setOpen(false)}>
              <X aria-hidden /> Close
            </Button>
          </div>
          <NavList onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>

      <div className="lg:pl-[260px]">
        <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1100px] px-4 py-8 sm:px-6">
          {children}
        </main>
        <footer className="mx-auto flex max-w-[1100px] flex-wrap justify-between gap-2 px-4 pb-8 text-base text-muted-foreground sm:px-6">
          <span>Keeper never moves real money in this demo.</span>
          <HealthLine />
        </footer>
      </div>
    </div>
  );
}
