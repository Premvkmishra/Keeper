import uuid
import pytest
from backend.app.core.config import settings
from backend.app.models.models import User, Household, HouseholdMember, Bill
from backend.app.security.passwords import hash_password, verify_password


def test_password_hashing():
    pwd = "SecurePassword123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert "$" in hashed
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_cors_preflight_for_frontend_origins(client):
    # Port 8081 development origin
    res = client.options(
        "/api/v1/me",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:8081"
    assert "GET" in res.headers.get("access-control-allow-methods", "")

    # Port 8080 development origin
    res8080 = client.options(
        "/api/v1/me",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert res8080.status_code == 200
    assert res8080.headers.get("access-control-allow-origin") == "http://localhost:8080"


def test_register_login_and_me_lifecycle(client):
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "SuperPassword123!"
    display_name = "Alice Test"

    # 1. Validation failure: mismatched passwords
    res_mismatch = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "display_name": display_name,
            "password": password,
            "confirm_password": "DifferentPassword123!",
        },
    )
    assert res_mismatch.status_code == 422
    assert "confirm_password" in str(res_mismatch.json())

    # 2. Validation failure: short password
    res_short = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "display_name": display_name,
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert res_short.status_code == 422

    # 3. Successful registration
    res_reg = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "display_name": display_name,
            "password": password,
            "confirm_password": password,
        },
    )
    assert res_reg.status_code == 201
    reg_data = res_reg.json()
    assert "token" in reg_data
    assert reg_data["user"]["email"] == unique_email
    assert reg_data["user"]["display_name"] == display_name
    assert "password" not in str(reg_data)
    assert "password_hash" not in str(reg_data)

    # 4. Duplicate registration rejected
    res_dup = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "display_name": "Another Name",
            "password": password,
            "confirm_password": password,
        },
    )
    assert res_dup.status_code == 409
    assert res_dup.json()["error"]["code"] == "duplicate_resource"

    # 5. Login with invalid password rejected
    res_bad_pw = client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": "WrongPassword!"},
    )
    assert res_bad_pw.status_code == 401
    assert res_bad_pw.json()["error"]["code"] == "unauthenticated"

    # 6. Login with valid credentials succeeds
    res_login = client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert res_login.status_code == 200
    token = res_login.json()["token"]
    assert token
    assert "password" not in str(res_login.json())
    assert "password_hash" not in str(res_login.json())

    # 7. Unauthenticated /api/v1/me returns 401
    res_unauth = client.get("/api/v1/me")
    assert res_unauth.status_code == 401

    # 8. Authenticated /api/v1/me returns user info
    res_me = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["email"] == unique_email
    assert me_data["display_name"] == display_name
    assert me_data["role"] == "owner"
    assert me_data["household"]["name"] == f"{display_name}'s Household"
    assert "password" not in str(me_data)
    assert "password_hash" not in str(me_data)

    # 9. Logout clears credentials
    res_logout = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_logout.status_code == 200


def test_multi_tenant_household_isolation(client):
    # Register User A
    user_a_email = f"user_a_{uuid.uuid4().hex[:8]}@test.com"
    res_a = client.post(
        "/api/v1/auth/register",
        json={
            "email": user_a_email,
            "display_name": "User A",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    assert res_a.status_code == 201
    token_a = res_a.json()["token"]
    household_a_id = res_a.json()["user"]["household"]["id"]

    # Register User B
    user_b_email = f"user_b_{uuid.uuid4().hex[:8]}@test.com"
    res_b = client.post(
        "/api/v1/auth/register",
        json={
            "email": user_b_email,
            "display_name": "User B",
            "password": "Password123!",
            "confirm_password": "Password123!",
        },
    )
    assert res_b.status_code == 201
    token_b = res_b.json()["token"]
    household_b_id = res_b.json()["user"]["household"]["id"]

    assert household_a_id != household_b_id

    # User A creates a bill
    res_bill_a = client.post(
        "/api/v1/bills",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "title": "User A Secret Electricity Bill",
            "category": "electricity",
            "amount": "2500.00",
            "currency": "INR",
            "due_date": "2026-11-01",
            "destination_account_number": "112233440001",
            "destination_ifsc": "HDFC0001234",
        },
    )
    assert res_bill_a.status_code == 201
    bill_a_id = res_bill_a.json()["id"]

    # User B lists bills: must NOT see User A's bill
    res_bills_b = client.get(
        "/api/v1/bills",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_bills_b.status_code == 200
    b_bill_ids = [b["id"] for b in res_bills_b.json()["items"]]
    assert bill_a_id not in b_bill_ids

    # User B attempts to access User A's bill directly by ID: must be rejected with 404
    res_get_a_by_b = client.get(
        f"/api/v1/bills/{bill_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res_get_a_by_b.status_code == 404
