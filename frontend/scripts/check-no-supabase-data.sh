#!/usr/bin/env bash
# Fails if the frontend uses Supabase for anything other than auth.
if grep -rnE "\.from\(['\"\`]|\.rpc\(|\.storage\b|\.channel\(|service_role|SERVICE_ROLE" src --include='*.ts' --include='*.tsx' | grep -v "routeTree.gen"; then
  echo "Forbidden Supabase data access found." >&2
  exit 1
fi
echo "OK: no Supabase data access."
