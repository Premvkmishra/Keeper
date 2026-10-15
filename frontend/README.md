# Keeper — frontend

Safe bill payments for older adults. Talks only to the Keeper FastAPI backend; Supabase is used for sign-in only. Demo — simulated bank, no real money.

## Setup

1. `npm install`
2. Copy `.env.example` to `.env` and fill in:
   - `VITE_API_BASE_URL` (no trailing slash; the app adds `/api/v1`)
   - `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (public anon key only)
3. `npm run dev`
4. Open `/login`, then sign in or create an account with email and password.
5. New accounts are assigned a private household and default safety policy automatically.
6. Confirm the email first if confirmation is enabled in Supabase Auth.

The backend must allow this frontend's origin via CORS.

## Production hosting (Railway frontend)

- Build command: `npm run build`
- Start command: `npm run start`
- Set `PORT` through Railway and configure `VITE_API_BASE_URL` to the public Render API URL and the two `VITE_SUPABASE_*` values at build time.
- Add the deployed Railway origin to the backend's `CORS_ORIGINS`.
- Set the Supabase Auth Site URL and allowed redirect URLs to the deployed frontend origin.
- Supabase's built-in email sender is limited to 2 emails per hour and only sends to project team addresses. Configure custom SMTP in Supabase Auth to send confirmation emails to Gmail and other recipients; do not disable email confirmation to work around rate limits.

## Checks

- `npm test` — unit tests (money, errors, labels, outcome panel, approve gating)
- `npm run check:no-supabase-data` — fails if any Supabase data call exists
