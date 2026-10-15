#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Find the correct Supabase connection pooler region."""
import sys, io, socket
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import psycopg

project = "amzllkpjwzqjrvudqxie"
password = "P%40ss%401234poiu"

regions = [
    "aws-0-ap-southeast-1",
    "aws-0-ap-southeast-2",
    "aws-0-ap-south-1",
    "aws-0-ap-northeast-1",
    "aws-0-ap-northeast-2",
    "aws-0-us-east-1",
    "aws-0-us-east-2",
    "aws-0-us-west-1",
    "aws-0-us-west-2",
    "aws-0-eu-central-1",
    "aws-0-eu-west-1",
    "aws-0-eu-west-2",
    "aws-0-ca-central-1",
    "aws-0-sa-east-1",
]

print(f"Trying {len(regions)} regions with port 6543 (transaction mode)...\n")

for r in regions:
    host = f"{r}.pooler.supabase.com"
    url = f"postgresql://postgres.{project}:{password}@{host}:6543/postgres"
    try:
        conn = psycopg.connect(url, connect_timeout=8)
        row = conn.execute("SELECT current_database(), version()").fetchone()
        conn.close()
        print(f"\nSUCCESS! Region: {r}")
        print(f"  DB      : {row[0]}")
        print(f"  Version : {str(row[1])[:60]}")
        print(f"\nPooler URL: postgresql://postgres.{project}:PASSWORD@{host}:6543/postgres")
        sys.exit(0)
    except Exception as e:
        msg = str(e)
        if "not found" in msg.lower() or "ENOTFOUND" in msg:
            result = "WRONG REGION"
        elif "password" in msg.lower() or "authentication" in msg.lower():
            result = "AUTH FAIL (right region? check password)"
        elif "timeout" in msg.lower():
            result = "TIMEOUT"
        elif "could not translate" in msg.lower() or "name resolution" in msg.lower():
            result = "DNS FAIL"
        else:
            result = f"ERR: {msg[:60]}"
        print(f"  {r:<30} -> {result}")

print("\nNo matching region found.")
