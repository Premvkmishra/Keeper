import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export const DEV_TOKEN =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1MSIsImVtYWlsIjoidTFAdGVzdC5jb20iLCJyb2xlIjoib3duZXIifQ.hqLEnEyv9wqSt7ekdDdgEg2o0G_UjFskf3KyJaEgq8k";

let client: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  return Boolean(
    import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY,
  );
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    sessionStorage.getItem("keeper_token") ||
    localStorage.getItem("keeper_token") ||
    localStorage.getItem("keeper_dev_token") ||
    null
  );
}

export function setAuthToken(token: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem("keeper_token", token);
  localStorage.setItem("keeper_token", token);
  localStorage.removeItem("keeper_dev_token");
}

export function clearAuthToken(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem("keeper_token");
  localStorage.removeItem("keeper_token");
  localStorage.removeItem("keeper_dev_token");
}

export function isDevAuth(): boolean {
  return Boolean(getAuthToken());
}

export function isAuthConfigured(): boolean {
  return isSupabaseConfigured() || isDevAuth();
}

export function getAuthClient(): SupabaseClient {
  if (!client) {
    const url = import.meta.env.VITE_SUPABASE_URL || "https://placeholder.supabase.co";
    const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || "placeholder-anon-key";
    client = createClient(url, anonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
      },
    });
  }
  return client;
}
