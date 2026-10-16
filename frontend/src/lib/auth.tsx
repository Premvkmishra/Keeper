import { createContext, useContext, type ReactNode } from "react";
import type { Me, Permissions } from "./types";

const MeContext = createContext<Me | null>(null);

export function MeProvider({ me, children }: { me: Me; children: ReactNode }) {
  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}

export function useMe(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error("useMe must be used inside MeProvider");
  return me;
}

export function usePermissions(): Permissions {
  return useMe().permissions;
}
