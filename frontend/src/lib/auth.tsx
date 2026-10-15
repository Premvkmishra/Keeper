import { createContext, useContext, type ReactNode } from "react";
import type { Me, Permissions } from "./types";

const MeContext = createContext<Me | null>(null);

export function MeProvider({
  value,
  children,
}: {
  value: Me;
  children: ReactNode;
}) {
  return <MeContext.Provider value={value}>{children}</MeContext.Provider>;
}

export function useMe(): Me {
  const ctx = useContext(MeContext);
  if (!ctx) {
    throw new Error("useMe must be used within a MeProvider");
  }
  return ctx;
}

export function usePermissions(): Permissions {
  const me = useMe();
  return me.permissions;
}
