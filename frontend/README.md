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

## Production hosting (Vercel)

- Set the Vercel project root directory to `frontend`.
- Use Node.js 24.x, the default install command, and `npm run build` as the build command. Nitro's Vercel preset generates the deployment output; do not configure a static output directory or start command.
- Configure `VITE_API_BASE_URL` as the public Render API URL (for example, `https://keeper-api-prod.onrender.com`, without a trailing slash), plus `VITE_SUPABASE_URL` and the public `VITE_SUPABASE_ANON_KEY`. These `VITE_*` values are embedded in the browser bundle at build time.
- Add the exact deployed Vercel origin to the backend's `CORS_ORIGINS`, preserving existing origins, then redeploy the backend.
- Set the Supabase Auth Site URL and allowed redirect URLs to the deployed frontend origin.
- Supabase's built-in email sender is limited to 2 emails per hour and only sends to project team addresses. Configure custom SMTP in Supabase Auth to send confirmation emails to Gmail and other recipients; do not disable email confirmation to work around rate limits.

## Checks

- `npm test` — unit tests (money, errors, labels, outcome panel, approve gating)
- `npm run check:no-supabase-data` — fails if any Supabase data call exists
