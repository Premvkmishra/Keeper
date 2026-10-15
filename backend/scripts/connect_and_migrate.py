#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keeper - Supabase Setup Script
Steps:
  1. Validate configuration
  2. Test connection to Supabase PostgreSQL
  3. Run schema migrations (idempotent)
  4. Seed dummy data (idempotent, uses ON CONFLICT DO NOTHING)
  5. Verify tables created
"""
import sys
import os
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT))

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not found. Run: pip install 'psycopg[binary]'")
    sys.exit(1)

from backend.app.core.config import settings

SUPABASE_DIR = Path(__file__).resolve().parents[1] / "supabase"

MIGRATIONS = [
    (1, "schema.sql"),
    (2, "migrations/002_processing_state.sql"),
    (3, "migrations/003_bill_documents.sql"),
    (4, "migrations/004_bill_processing_key.sql"),
]

LINE = "=" * 60


def step(n: int, title: str) -> None:
    print(f"\n{LINE}")
    print(f"  STEP {n}: {title}")
    print(LINE)


def get_psycopg_url() -> str:
    url = settings.SUPABASE_DB_URL or ""
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def main() -> int:
    print(f"\n{LINE}")
    print("  Keeper -> Supabase  Connection & Migration")
    print(LINE)

    # -- Step 1: Validate config -----------------------------------------------
    step(1, "Validate Configuration")
    if not settings.SUPABASE_DB_URL:
        print("FAIL: SUPABASE_DB_URL is not set in .env")
        return 1
    raw_url = settings.SUPABASE_DB_URL
    masked = raw_url[:35] + "..." if len(raw_url) > 35 else raw_url
    print(f"  OK  SUPABASE_DB_URL found")
    print(f"      URL  : {masked}")
    print(f"      Host : db.amzllkpjwzqjrvudqxie.supabase.co")
    print(f"      Port : 5432")
    print(f"      DB   : postgres")

    db_url = get_psycopg_url()

    # -- Step 2: Test Connection ------------------------------------------------
    step(2, "Test Database Connection")
    try:
        with psycopg.connect(db_url, connect_timeout=15) as conn:
            row = conn.execute("SELECT version(), NOW()").fetchone()
            pg_version = str(row[0])[:70]
            server_time = str(row[1])
            print(f"  OK  Connected successfully!")
            print(f"      PostgreSQL : {pg_version}")
            print(f"      Server time: {server_time}")
    except Exception as e:
        print(f"  FAIL  Connection failed: {e}")
        return 1

    # -- Step 3: Schema Migrations ---------------------------------------------
    step(3, "Run Schema Migrations")
    try:
        with psycopg.connect(db_url) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS keeper_schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"
            )
            applied = {
                row[0]
                for row in conn.execute(
                    "SELECT version FROM keeper_schema_migrations"
                ).fetchall()
            }
            print(f"  Already applied versions: {sorted(applied) if applied else 'none'}\n")

            applied_count = 0
            for version, relative_path in MIGRATIONS:
                sql_file = SUPABASE_DIR / relative_path
                if version in applied:
                    print(f"  SKIP  v{version} ({relative_path}) - already applied")
                    continue
                if not sql_file.exists():
                    print(f"  WARN  v{version} file not found: {sql_file} - skipping")
                    continue
                sql = sql_file.read_text(encoding="utf-8")
                conn.execute(sql, prepare=False)
                conn.execute(
                    "INSERT INTO keeper_schema_migrations (version) VALUES (%s)",
                    (version,),
                )
                print(f"  OK    v{version} applied  <-- {relative_path}")
                applied_count += 1

            if applied_count == 0:
                print("\n  OK  All migrations already up-to-date.")
            else:
                print(f"\n  OK  {applied_count} new migration(s) applied.")
    except Exception as e:
        print(f"  FAIL  Migration error: {e}")
        return 1

    # -- Step 4: Seed Data -----------------------------------------------------
    step(4, "Seed Dummy Data")
    try:
        seed_file = SUPABASE_DIR / "seed.sql"
        if not seed_file.exists():
            print(f"  WARN  seed.sql not found, skipping.")
        else:
            seed_sql = seed_file.read_text(encoding="utf-8")
            with psycopg.connect(db_url) as conn:
                conn.execute(seed_sql, prepare=False)
            print("  OK  Seed data applied (ON CONFLICT DO NOTHING - safe to re-run)")
            print()
            print("  Seeded records:")
            print("    - Household    : 'Demo Senior Household' (00000000-...-0001)")
            print("    - Policy       : auto_pay_limit=10000 INR, ttl=1440 min")
            print("    - Billers      : City Electricity, Safe Insurance")
            print("    - Beneficiaries: 2 active bank accounts")
            print("    - Bills        : 2 sample bills (electricity + insurance)")
    except Exception as e:
        print(f"  FAIL  Seed error: {e}")
        return 1

    # -- Step 5: Verify Tables -------------------------------------------------
    step(5, "Verify Tables in Supabase")
    try:
        with psycopg.connect(db_url) as conn:
            rows = conn.execute(
                """
                SELECT table_name,
                       (SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_name = t.table_name
                          AND table_schema = 'public') AS col_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            ).fetchall()
            print(f"\n  {'Table Name':<40} {'Columns':>7}")
            print(f"  {'-'*40} {'-'*7}")
            for name, cols in rows:
                print(f"  {name:<40} {cols:>7}")
    except Exception as e:
        print(f"  WARN  Could not verify tables: {e}")

    # -- Done ------------------------------------------------------------------
    print(f"\n{LINE}")
    print("  SUCCESS: Backend is connected to Supabase PostgreSQL!")
    print(f"{LINE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
