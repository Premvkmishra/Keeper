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
├── mock_bank/               # Standalone simulated bank ledger (port 9000)
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
- `SUPABASE_JWT_SECRET`: Supabase JWT signature verifier. The API rejects unsigned JWTs and refuses normal startup without it.
- `SUPABASE_URL`: Supabase project URL (`https://amzllkpjwzqjrvudqxie.supabase.co`).
- `MOCK_BANK_BASE_URL`: Mock bank URL (default: `http://127.0.0.1:9000`).
- `MOCK_BANK_AUTH_TOKEN`: Separate bearer secret shared between the backend and simulator.
- `ARMORIQ_ENFORCEMENT=required` and `ARMORIQ_ROUTE=proxy`; all other modes block processing.
- `ARMORIQ_API_KEY`: Server-side ArmorIQ API key.
- `KEEPER_MCP_PUBLIC_URL`: Public HTTPS MCP URL ending in `/mcp`, registered in ArmorIQ.
- `KEEPER_MCP_INBOUND_SECRET`: Shared secret for bearer authentication on `/mcp`.
- `GEMINI_API_KEY`: Server-side Gemini API key.

---

## Initialize Supabase

From `backend/`, with `SUPABASE_DB_URL` available through `.env` or the process environment:

```powershell
.\.venv\Scripts\python.exe scripts\setup_supabase.py
```

The command applies four versioned, non-destructive migrations and inserts only missing seed records. Seeded bills remain pending; no payment or Witness outcome is fabricated. API startup verifies migration version 4.

## Running Locally

### 1. Start Mock Bank (Port 9000)

```powershell
.\.venv\Scripts\python.exe -m uvicorn mock_bank.main:app --port 9000
```

### 2. Start Keeper Backend (Port 8000)

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Verify health check:
```powershell
curl http://127.0.0.1:8000/health
```

### 3. Running with Docker Compose

```bash
cd backend
docker-compose up --build
```

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
