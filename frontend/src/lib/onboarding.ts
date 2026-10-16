import { api } from "./api";
import { getAuthClient } from "./supabase";

function metadataText(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

export async function ensureHouseholdForCurrentUser(profile?: {
  displayName?: string;
  householdName?: string;
}): Promise<void> {
  const { data, error } = await getAuthClient().auth.getUser();
  if (error) throw error;
  if (!data.user?.id || !data.user.email) {
    throw new Error("Your sign-in session is missing its account identity. Please sign in again.");
  }

  const metadata = data.user.user_metadata ?? {};
  const displayName =
    profile?.displayName ??
    metadataText(metadata["display_name"]) ??
    data.user.email.split("@")[0] ??
    "Keeper user";
  const householdName =
    profile?.householdName ??
    metadataText(metadata["household_name"]) ??
    `${displayName}'s household`;

  await api.bootstrapHousehold({
    display_name: displayName,
    household_name: householdName,
  });
}
