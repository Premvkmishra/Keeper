"""Mock Bank Service.
Authoritative simulated bank ledger for Keeper.
Operates on an isolated SQLite database.
"""
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
from dotenv import dotenv_values

DB_PATH = os.environ.get("MOCK_BANK_DATABASE_PATH", "backend/mock_bank/bank.sqlite")
MOCK_BANK_AUTH_TOKEN = os.environ.get("MOCK_BANK_AUTH_TOKEN") or dotenv_values(
    Path(__file__).resolve().parents[1] / ".env"
).get("MOCK_BANK_AUTH_TOKEN")

app = FastAPI(title="Keeper Mock Bank", version="1.0.0")

def get_db_path() -> Path:
    p = Path(DB_PATH)
    if not p.is_absolute():
        # Relative to repository root or backend
        repo_root = Path(__file__).resolve().parent.parent.parent
        p = (repo_root / DB_PATH).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def init_bank_db():
    p = get_db_path()
    with sqlite3.connect(p) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank_txn_id TEXT NOT NULL UNIQUE,
                client_reference TEXT NOT NULL UNIQUE,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL,
                destination_account_number TEXT NOT NULL,
                destination_account_number_masked TEXT NOT NULL,
                destination_ifsc TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'posted',
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_client_ref ON transactions(client_reference)")
        conn.commit()

@app.on_event("startup")
def startup_event():
    init_bank_db()

class PaymentRequest(BaseModel):
    client_reference: str = Field(..., min_length=1, max_length=128)
    amount: str = Field(..., pattern=r"^\d+(\.\d{2})?$")
    currency: str = Field(default="INR", max_length=3)
    destination_account_number: str = Field(..., min_length=6, max_length=34)
    destination_ifsc: str = Field(..., min_length=11, max_length=11)

class PaymentResponse(BaseModel):
    bank_txn_id: str
    client_reference: str
    amount: str
    currency: str
    destination_account_number_masked: str
    destination_ifsc: str
    status: str
    created_at: str

def mask_account(num: str) -> str:
    if len(num) <= 4:
        return f"••••{num}"
    return f"••••••••{num[-4:]}"

def require_backend_authorization(authorization: Optional[str] = Header(None)) -> None:
    expected = MOCK_BANK_AUTH_TOKEN
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not expected or not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Backend authorization required.")

@app.get("/health")
def health():
    try:
        p = get_db_path()
        with sqlite3.connect(p) as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "service": "mock_bank", "ledger": "sqlite"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database check failed: {str(e)}")

from fastapi import FastAPI, HTTPException, status, Response

@app.post(
    "/bank/v1/payments",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_backend_authorization)],
)
def record_payment(req: PaymentRequest, response: Response = None):
    p = get_db_path()
    masked = mask_account(req.destination_account_number)
    # Ensure amount has 2 decimal places
    amount_str = f"{float(req.amount):.2f}"

    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Idempotency check on client_reference
        cursor.execute("SELECT * FROM transactions WHERE client_reference = ?", (req.client_reference,))
        existing = cursor.fetchone()
        
        if existing:
            # Check if payload matches
            if (
                existing["amount"] == amount_str
                and existing["currency"] == req.currency
                and existing["destination_account_number"] == req.destination_account_number
                and existing["destination_ifsc"] == req.destination_ifsc
            ):
                if response:
                    response.status_code = status.HTTP_200_OK
                return PaymentResponse(
                    bank_txn_id=existing["bank_txn_id"],
                    client_reference=existing["client_reference"],
                    amount=existing["amount"],
                    currency=existing["currency"],
                    destination_account_number_masked=existing["destination_account_number_masked"],
                    destination_ifsc=existing["destination_ifsc"],
                    status=existing["status"],
                    created_at=existing["created_at"],
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="client_reference exists with different payment details",
                )

        bank_txn_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        
        cursor.execute(
            """
            INSERT INTO transactions (
                bank_txn_id, client_reference, amount, currency,
                destination_account_number, destination_account_number_masked,
                destination_ifsc, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'posted', ?)
            """,
            (
                bank_txn_id,
                req.client_reference,
                amount_str,
                req.currency,
                req.destination_account_number,
                masked,
                req.destination_ifsc,
                now_iso,
            ),
        )
        conn.commit()

        return PaymentResponse(
            bank_txn_id=bank_txn_id,
            client_reference=req.client_reference,
            amount=amount_str,
            currency=req.currency,
            destination_account_number_masked=masked,
            destination_ifsc=req.destination_ifsc,
            status="posted",
            created_at=now_iso,
        )

@app.get(
    "/bank/v1/payments/{client_reference}",
    response_model=PaymentResponse,
    dependencies=[Depends(require_backend_authorization)],
)
def get_payment(client_reference: str):
    p = get_db_path()
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transactions WHERE client_reference = ?", (client_reference,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found for client_reference")
        return PaymentResponse(
            bank_txn_id=row["bank_txn_id"],
            client_reference=row["client_reference"],
            amount=row["amount"],
            currency=row["currency"],
            destination_account_number_masked=row["destination_account_number_masked"],
            destination_ifsc=row["destination_ifsc"],
            status=row["status"],
            created_at=row["created_at"],
        )
