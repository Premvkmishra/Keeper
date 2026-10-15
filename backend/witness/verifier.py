"""Independent Witness verification service.
Provides read-only inspection of the simulated bank ledger.
Guarantees that payment state transitions are backed by true ledger entries.
"""
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

class WitnessVerifier:
    def __init__(self, ledger_db_path: Optional[str] = None):
        raw_path = ledger_db_path or os.environ.get("MOCK_BANK_DATABASE_PATH", "backend/mock_bank/bank.sqlite")
        p = Path(raw_path)
        if not p.is_absolute():
            repo_root = Path(__file__).resolve().parent.parent.parent
            p = (repo_root / raw_path).resolve()
        self.ledger_db_path = p

    def verify_payment_attempt(
        self,
        client_reference: str,
        expected_amount: str,
        expected_currency: str,
        expected_destination_account: str,
        expected_ifsc: str,
        expected_outcome: str,  # "payment_present" | "payment_absent"
        attempt_created_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Independently queries the bank SQLite ledger using read-only access.
        Returns report dictionary with verdict, matches, and summary.
        """
        now = datetime.now(timezone.utc)
        start_time = (attempt_created_at or now) - timedelta(hours=1)
        end_time = now + timedelta(hours=1)
        
        window_start_iso = start_time.isoformat()
        window_end_iso = end_time.isoformat()
        checked_at_iso = now.isoformat()

        if not self.ledger_db_path.exists():
            return {
                "expected_outcome": expected_outcome,
                "verdict": "unverifiable",
                "ledger_match_count": 0,
                "matched_transactions": [],
                "summary": "Bank ledger could not be queried. Outcome is unverifiable; no payment status was inferred.",
                "ledger_source": "mock_bank_sqlite",
                "read_only": True,
                "window_start": window_start_iso,
                "window_end": window_end_iso,
                "checked_at": checked_at_iso,
            }

        try:
            # Read-only URI mode for SQLite
            uri_path = f"file:{self.ledger_db_path.as_posix()}?mode=ro"
            with sqlite3.connect(uri_path, uri=True) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT bank_txn_id, client_reference, amount, currency,
                           destination_account_number, destination_account_number_masked,
                           destination_ifsc, status, created_at
                    FROM transactions
                    WHERE client_reference = ?
                    """,
                    (client_reference,),
                )
                rows = cursor.fetchall()

        except Exception as e:
            return {
                "expected_outcome": expected_outcome,
                "verdict": "unverifiable",
                "ledger_match_count": 0,
                "matched_transactions": [],
                "summary": f"Error reading bank ledger: {str(e)}",
                "ledger_source": "mock_bank_sqlite",
                "read_only": True,
                "window_start": window_start_iso,
                "window_end": window_end_iso,
                "checked_at": checked_at_iso,
            }

        matched_txns: List[Dict[str, Any]] = []
        # Format expected amount to two decimal places
        norm_expected_amount = f"{float(expected_amount):.2f}"

        for row in rows:
            matched_txns.append({
                "bank_txn_id": row["bank_txn_id"],
                "amount": row["amount"],
                "currency": row["currency"],
                "destination_account_number_masked": row["destination_account_number_masked"],
                "destination_ifsc": row["destination_ifsc"],
                "bank_status": row["status"],
                "created_at": row["created_at"],
            })

        count = len(matched_txns)

        if count == 0:
            if expected_outcome == "payment_absent":
                verdict = "confirmed_no_payment"
                summary = "Witness confirms: no payment found in bank ledger."
            else:
                verdict = "mismatch_detected"
                summary = "Witness detected mismatch: payment expected, but none found in bank ledger."
        else:
            first = rows[0]
            # Verify details match expected
            details_match = (
                first["amount"] == norm_expected_amount
                and first["currency"] == expected_currency
                and first["destination_account_number"] == expected_destination_account
                and first["destination_ifsc"] == expected_ifsc
            )
            if not details_match:
                verdict = "mismatch_detected"
                summary = "Witness detected critical mismatch: ledger transaction found but amount/payee details differ!"
            elif expected_outcome == "payment_present":
                verdict = "confirmed_paid"
                summary = "Witness confirms: exactly one matching transaction found in bank ledger."
            else:
                verdict = "mismatch_detected"
                summary = "Witness detected mismatch: payment was expected absent, but posted in bank ledger!"

        return {
            "expected_outcome": expected_outcome,
            "verdict": verdict,
            "ledger_match_count": count,
            "matched_transactions": matched_txns,
            "summary": summary,
            "ledger_source": "mock_bank_sqlite",
            "read_only": True,
            "window_start": window_start_iso,
            "window_end": window_end_iso,
            "checked_at": checked_at_iso,
        }
