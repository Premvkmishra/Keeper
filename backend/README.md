# Keeper Backend & Security Engine

Autonomous bill-payment backend with defense-in-depth policy enforcement, ArmorIQ v2 agent proxy authorization, simulated bank ledger, and independent Witness verification.

> **CRITICAL NOTICE**: All payments in Keeper are strictly simulated. No real money or actual banking rails are ever connected.

---

## Architecture & Trust Boundaries

Keeper enforces **7 strict security boundaries**:

1. **AI Agent Boundary (Untrusted)**: Proposes bill payments via MCP tools. Cannot directly execute payments or modify beneficiaries.
2. **ArmorIQ Policy Proxy Boundary**: Validates tool invocation via signed intent plan & 60s intent tokens. Denies policy violations before Keeper services are reached.
3. **Inbound MCP Security**: Enforces constant-time bearer verification and a short-lived HMAC-signed household context derived by the authenticated backend.
4. **Authoritative Keeper Policy Engine**: Checks trusted billers, verified beneficiaries, household policy limits, and exact payment details hash (`details_hash`).
5. **Human Explicit Approval**: Required for payments exceeding household thresholds (e.g. ₹10,000). Agent cannot approve its own payments.
6. **Authoritative Payment Execution Service & Mock Bank**: Single protected execution path with database-level idempotency (`client_reference` / `idempotency_key`). Mock bank ledger is isolated in SQLite.
7. **Independent Witness**: Independent read-only verification against the mock bank ledger. Confirms actual state transition before payment is reported as confirmed.

---

## Directory Structure

```text
backend/
├── app/
│   ├── main.py              # FastAPI application with CORS and middleware
│   ├── api/                 # REST endpoints (/api/v1) and MCP server (/mcp)
│   ├── core/                # Config, database engine, Supabase JWT auth
│   ├── models/              # SQLAlchemy ORM models for 11 persisted tables
│   ├── schemas/             # Typed Pydantic v2 schemas
│   ├── services/            # Policy engine, payment execution, agent, witness
│   └── integrations/        # ArmorIQ v2 Gateway (lifespan, proxy, token minting)
├── mock_bank/               # Embedded simulated bank API and SQLite ledger
├── witness/                 # Independent read-only bank ledger verifier
├── armoriq/                 # MCP configuration (armoriq.yaml)
├── scripts/                 # SDK verification, registration, run scripts
├── supabase/                # Canonical schema.sql and seed.sql
├── tests/                   # Backend, offline U1-U11, and live L1-L8 test suites
├── Dockerfile               # Backend containerfile
├── Dockerfile.mockbank      # Mock bank containerfile
├── docker-compose.yml       # Complete local service composition
└── pyproject.toml           # Backend dependencies and project configuration
```

---

## Prerequisites

- **Python**: 3.11 (Python 3.11.4 verified)
- **Node.js**: >= 20.x for frontend
- **Docker & Docker Compose** (Optional, for containerized run)

---

## Setup & Virtual Environment

An isolated virtual environment is mandatory.

### Windows (PowerShell)

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

If execution policies block activation:
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

### macOS / Linux

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

---

## Environment Configuration

Copy `backend/.env.example` to `backend/.env`:

```bash
cp .env.example .env
```

Required variables:
- `SUPABASE_DB_URL`: Supabase PostgreSQL connection string. Required outside isolated tests.
- `SUPABASE_JWT_SECRET`: Supabase legacy JWT verifier and signing key for short-lived MCP household contexts. Use the Supabase JWT secret; never commit it.
- `SUPABASE_URL`: Supabase project URL (`https://amzllkpjwzqjrvudqxie.supabase.co`).
- `MOCK_BANK_AUTH_TOKEN`: Bearer secret protecting the backend's internal mock-bank routes.
- `ARMORIQ_ENFORCEMENT=required` and `ARMORIQ_ROUTE=proxy`; all other modes block processing.
- `ARMORIQ_API_KEY`: Server-side ArmorIQ API key.
- `KEEPER_MCP_PUBLIC_URL`: Public HTTPS MCP URL ending in `/mcp`, registered in ArmorIQ.
- `KEEPER_MCP_INBOUND_SECRET`: Shared secret for bearer authentication on `/mcp`.
- `LLM_PROVIDER`: Agent LLM provider, `groq` (default) or `gemini`.
- `GROQ_API_KEY`: Server-side Groq API key; keep it out of source control.
- `GROQ_MODEL`: Primary Groq model (default: `openai/gpt-oss-20b`).
- `GROQ_FALLBACK_MODELS`: Comma-separated Groq fallback models (default: `openai/gpt-oss-120b`). Transient failures retry the primary, then try each fallback once; all configured models must support tool use.
- `GEMINI_API_KEY`: Server-side Gemini API key when `LLM_PROVIDER=gemini`.
- `GEMINI_MODEL`: Primary Gemini model (default: `gemini-2.5-flash`).
- `GEMINI_FALLBACK_MODELS`: Comma-separated Gemini fallback models (default: `gemini-2.5-flash-lite,gemini-2.5-pro`). Transient failures retry the primary, then try each fallback once; all models must support the configured tool-calling request.

The agent uses Groq by default and retains the Gemini Developer API as an alternative. Groq tool calls are handled by the backend and still execute through ArmorIQ; the provider change does not bypass authorization or payment policy. Groq model availability can change; configure only model IDs enabled for your Groq account.

The frontend uses Supabase Auth email/password sign-in and sign-up. New accounts create a private household and default policy after authentication; Supabase email confirmation may need to be completed before sign-in, depending on the project’s Auth settings. There is no built-in demo-token login fallback.

---

## Initialize Supabase

From `backend/`, with `SUPABASE_DB_URL` available through `.env` or the process environment:

```powershell
.\.venv\Scripts\python.exe scripts\setup_supabase.py
```

The command applies five versioned, non-destructive migrations and inserts only missing seed records. Seeded bills remain pending; no payment or Witness outcome is fabricated. API startup verifies migration version 5. Migration 5 requires each authenticated user to belong to at most one household.

## Running Locally

### Start Keeper Backend (Port 8000)

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Verify health check:
```powershell
curl http://127.0.0.1:8000/health
```

The mock bank API is embedded in the Keeper backend; do not start another Uvicorn process for it.

### Running with Docker Compose

```bash
cd backend
docker-compose up --build
```

## Production hosting (Render)

For one Render web service, Keeper mounts the simulated bank inside the same FastAPI application. Only the Keeper API process and public port are needed; do not create or start a separate mock-bank service.

- **Docker deployment**: set the root directory to `backend` and use `./Dockerfile`.
- **Native Python deployment**: set the root directory to `backend`, build with `pip install .`, and start with `sh render-start.sh`.
- Set the health check path to `/health`.
- Attach a persistent disk mounted at `/var/data`; set `MOCK_BANK_DATABASE_PATH=/var/data/bank_ledger.db`.
- `ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN`, when set, must exactly match `KEEPER_MCP_INBOUND_SECRET`; Keeper now rejects a mismatch instead of reporting the ArmorIQ integration healthy.
- Configure backend secrets in Render's environment settings, not in a committed `.env`. Set `MOCK_BANK_AUTH_TOKEN` to a strong random value, `ARMORIQ_ENFORCEMENT=required`, `ARMORIQ_ROUTE=proxy`, and `KEEPER_MCP_PUBLIC_URL` to the Render HTTPS URL ending in `/mcp`. Any legacy `MOCK_BANK_BASE_URL` setting is ignored; bank traffic uses the backend's internal mock-bank routes.
- Set `KEEPER_MCP_INBOUND_SECRET` to a strong random bearer token. Configure the ArmorIQ MCP registry to send that exact token as its Bearer token. If `ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN` is set, it must match the registry token too.
- Set `CORS_ORIGINS` to the exact Railway frontend origin. Set the frontend build-time `VITE_API_BASE_URL` to the Render API origin and configure Supabase Auth's Site URL/redirect URLs for the Railway domain.

The mock bank uses a local SQLite ledger shared with the Witness verifier. It runs in the same application process as the API and stores its ledger on the persistent disk. Do not scale this single-instance SQLite setup horizontally. Supabase remains the PostgreSQL database; the local mock bank is a payment simulator only.

---

## ArmorIQ v2 Integration Details

- **SDK Version**: `armoriq-sdk==0.6.10` verified against Python 3.11.
- **Verification Script**: Run `python scripts/verify_armoriq_sdk.py` to confirm SDK signatures (`ArmorIQClient`, `capture_plan`, `get_intent_token`, `invoke`).
- **MCP endpoint**: `POST /mcp`, JSON-RPC 2.0 with SSE responses and bearer `KEEPER_MCP_INBOUND_SECRET`. Supports `initialize`, `notifications/initialized`, `ping`, `tools/list`, and `tools/call`.
- **MCP Server Surface**: Exactly 4 tools exposed under `keeper-payments`:
  1. `list_bills`
  2. `get_bill`
  3. `propose_payment`
  4. `get_payment_status`
- Only required proxy enforcement can execute tools. Keeper uses the SDK's ArmorIQ proxy default; the public Keeper MCP URL is configured in the server registry, not as `proxy_endpoint`.
- Register using `scripts/armoriq_register.ps1` or `.sh` only after public HTTPS is available. Verify CLI `status` and active platform policies. Do not treat a local SDK test as proof of registration.

---

## Automated Tests

Run backend test suite:

```powershell
.\.venv\Scripts\pytest.exe -v tests
```

Offline tests cover:
- Core backend invariants, household isolation, beneficiary denial, approval resumption.
- Tests U1 through U11 verifying all ArmorIQ offline scenarios.
- Mock bank duplicate protection and independent Witness verification.
