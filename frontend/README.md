# Keeper — frontend

Safe bill payments for older adults. Talks only to the Keeper FastAPI backend; Supabase is used for sign-in only. Demo — simulated bank, no real money.

## Setup

1. `npm install`
2. Copy `.env.example` to `.env` and fill in:
   - `VITE_API_BASE_URL` (no trailing slash; the app adds `/api/v1`)
   - `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (public anon key only)
3. `npm run dev`
4. Create an account on `/login`.
5. Ask the setup person to run the SQL bootstrap (`bootstrap_household`) for your user.
6. Sign in again and open **Demo scenarios**.

The backend must allow this frontend's origin via CORS.

## Checks

- `npm test` — unit tests (money, errors, labels, outcome panel, approve gating)
- `npm run check:no-supabase-data` — fails if any Supabase data call exists
