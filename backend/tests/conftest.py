import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment
from pathlib import Path
_repo_root = Path(__file__).resolve().parent.parent.parent
os.environ["APP_ENV"] = "testing"
os.environ["SUPABASE_JWT_SECRET"] = "keeper-test-only-secret-key-with-more-than-32-bytes"
os.environ["KEEPER_MCP_INBOUND_SECRET"] = "keeper-test-mcp-secret"
os.environ["ARMORIQ_ENFORCEMENT"] = "disabled"
os.environ["MOCK_BANK_BASE_URL"] = "http://mock-bank.disabled.test"
os.environ["MOCK_BANK_DATABASE_PATH"] = str((_repo_root / "backend" / "mock_bank" / "test_bank.sqlite").resolve())
os.environ["MOCK_BANK_AUTH_TOKEN"] = "test-mock-bank-token"

from backend.app.core.database import Base, get_db
from backend.app.core.config import settings
from backend.app.main import app
from backend.app.models.models import (
    Household,
    HouseholdMember,
    HouseholdPolicy,
    TrustedBiller,
    ApprovedBeneficiary,
    Bill,
    PaymentApproval,
    PaymentAttempt,
    SecurityEvent,
)
from backend.mock_bank.main import app as mock_bank_app, get_db_path as get_bank_db_path

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture
def db(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestingSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def mock_bank_client():
    import sqlite3
    p = get_bank_db_path()
    from backend.mock_bank.main import init_bank_db
    init_bank_db()
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM transactions")
        conn.commit()

    with TestClient(mock_bank_app) as c:
        yield c

    try:
        with sqlite3.connect(p) as conn:
            conn.execute("DELETE FROM transactions")
            conn.commit()
    except Exception:
        pass

@pytest.fixture
def seed_data(db):
    now = datetime.now(timezone.utc)
    # Default household
    h1 = Household(id=settings.MCP_AGENT_HOUSEHOLD_ID, name="Test Household", currency="INR")
    # Alternate household for isolation tests
    h2 = Household(id=str(uuid.uuid4()), name="Other Household", currency="INR")
    db.add_all([h1, h2])
    db.commit()

    # Owner for h1
    owner_user_id = str(uuid.uuid4())
    m1 = HouseholdMember(
        household_id=h1.id,
        user_id=owner_user_id,
        email="owner@test.com",
        display_name="Test Owner",
        role="owner",
    )
    # Caregiver for h1
    caregiver_user_id = str(uuid.uuid4())
    m2 = HouseholdMember(
        household_id=h1.id,
        user_id=caregiver_user_id,
        email="caregiver@test.com",
        display_name="Test Caregiver",
        role="caregiver",
    )
    # Viewer for h1
    viewer_user_id = str(uuid.uuid4())
    m3 = HouseholdMember(
        household_id=h1.id,
        user_id=viewer_user_id,
        email="viewer@test.com",
        display_name="Test Viewer",
        role="viewer",
    )
    # User for h2
    h2_user_id = str(uuid.uuid4())
    m4 = HouseholdMember(
        household_id=h2.id,
        user_id=h2_user_id,
        email="other@test.com",
        display_name="Other User",
        role="owner",
    )
    db.add_all([m1, m2, m3, m4])

    # Policies
    pol1 = HouseholdPolicy(
        household_id=h1.id,
        auto_pay_limit=10000.00,
        currency="INR",
        approval_ttl_minutes=1440,
        version=1,
        updated_by_name="Test Owner",
    )
    pol2 = HouseholdPolicy(
        household_id=h2.id,
        auto_pay_limit=5000.00,
        currency="INR",
        approval_ttl_minutes=1440,
        version=1,
        updated_by_name="Other User",
    )
    db.add_all([pol1, pol2])

    # Trusted Billers for h1
    biller = TrustedBiller(
        household_id=h1.id,
        name="State Electricity Board",
        category="electricity",
        status="active",
    )
    db.add(biller)
    db.commit()
    db.refresh(biller)

    # Approved Beneficiary for h1
    ben = ApprovedBeneficiary(
        household_id=h1.id,
        biller_id=biller.id,
        display_name="Electricity Board Direct",
        account_number="112233440101",
        account_number_masked="••••••••0101",
        ifsc="HDFC0001234",
        status="active",
    )
    db.add(ben)
    db.commit()

    return {
        "h1": h1,
        "h2": h2,
        "owner_id": owner_user_id,
        "caregiver_id": caregiver_user_id,
        "viewer_id": viewer_user_id,
        "h2_user_id": h2_user_id,
        "biller": biller,
        "ben": ben,
    }

def make_auth_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
