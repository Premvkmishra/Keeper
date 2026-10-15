import { createContext, useContext, type ReactNode } from "react";
import type { Me, Permissions } from "./types";

const MeContext = createContext<Me | null>(null);

export function MeProvider({
  value,
  me,
  children,
}: {
  value?: Me;
  me?: Me;
  children: ReactNode;
}) {
  const current = value ?? me ?? null;
  return <MeContext.Provider value={current}>{children}</MeContext.Provider>;
}

export function useMe(): Me {
  const ctx = useContext(MeContext);
  if (!ctx) {
    throw new Error("useMe must be used within a MeProvider");
  }
  return ctx;
}

export function useOptionalMe(): Me | null {
  return useContext(MeContext);
}

export function usePermissions(): Permissions {
  const me = useMe();
  return me.permissions;
}
