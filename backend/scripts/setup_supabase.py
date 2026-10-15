#!/usr/bin/env python3
"""Apply versioned Keeper schema changes and idempotent seed data to Supabase."""
import sys
from pathlib import Path

import psycopg

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.core.config import settings

SUPABASE_DIR = Path(__file__).resolve().parents[1] / "supabase"
MIGRATIONS = (
    (1, "schema.sql"),
    (2, "migrations/002_processing_state.sql"),
    (3, "migrations/003_bill_documents.sql"),
    (4, "migrations/004_bill_processing_key.sql"),
)


def main() -> int:
    if not settings.SUPABASE_DB_URL:
        print("SUPABASE_DB_URL is missing; no database changes were made.", file=sys.stderr)
        return 2

    database_url = settings.SUPABASE_DB_URL
    if database_url.startswith("postgresql+psycopg://"):
        database_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    with psycopg.connect(database_url) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS keeper_schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM keeper_schema_migrations"
            ).fetchall()
        }

        for version, relative_path in MIGRATIONS:
            if version in applied:
                continue
            sql = (SUPABASE_DIR / relative_path).read_text(encoding="utf-8")
            connection.execute(sql, prepare=False)
            connection.execute(
                "INSERT INTO keeper_schema_migrations (version) VALUES (%s)",
                (version,),
            )
            print(f"Applied migration {version}: {relative_path}")

        seed_sql = (SUPABASE_DIR / "seed.sql").read_text(encoding="utf-8")
        connection.execute(seed_sql, prepare=False)
        print("Seed data is present (existing records were not overwritten).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())