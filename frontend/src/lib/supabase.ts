// Supabase is used only for authentication (no data, RPC, storage, or realtime).
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

export function isSupabaseConfigured(): boolean {
  return Boolean(import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY);
}

export function getAuthClient(): SupabaseClient {
  if (client) return client;
  const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
  const key = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;
  if (!url || !key)
    throw new Error("Sign-in is not configured (VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY).");
  client = createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } });
  return client;
}

export async function getAccessToken(): Promise<string | null> {
  if (typeof window === "undefined" || !isSupabaseConfigured()) return null;
  const { data } = await getAuthClient().auth.getSession();
  return data.session?.access_token ?? null;
}
