"""Non-destructive local seed for SQLite development databases."""
import logging
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.models import (
    ApprovedBeneficiary,
    Household,
    HouseholdMember,
    HouseholdPolicy,
    TrustedBiller,
)

logger = logging.getLogger(__name__)

DEMO_HOUSEHOLD_ID = "00000000-0000-0000-0000-000000000001"
DEMO_OWNER_USER_ID = "u1"
DEMO_OWNER_EMAIL = "u1@test.com"


def seed_demo_household(db: Session) -> None:
    """Insert demo household data if missing. Never deletes or overwrites existing rows."""
    hid = settings.MCP_AGENT_HOUSEHOLD_ID or DEMO_HOUSEHOLD_ID
    household = db.query(Household).filter(Household.id == hid).first()
    if not household:
        household = Household(id=hid, name="Demo Senior Household", currency="INR")
        db.add(household)
        db.flush()
        logger.info("Seeded demo household %s", hid)

    if not db.query(HouseholdPolicy).filter(HouseholdPolicy.household_id == hid).first():
        db.add(
            HouseholdPolicy(
                household_id=hid,
                auto_pay_limit=10000.00,
                currency="INR",
                approval_ttl_minutes=1440,
                version=1,
                updated_by_name="System Seed",
            )
        )

    member = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == hid, HouseholdMember.email == DEMO_OWNER_EMAIL)
        .first()
    )
    if not member:
        db.add(
            HouseholdMember(
                household_id=hid,
                user_id=DEMO_OWNER_USER_ID,
                email=DEMO_OWNER_EMAIL,
                display_name="Demo Owner",
                role="owner",
            )
        )

    elec = (
        db.query(TrustedBiller)
        .filter(TrustedBiller.household_id == hid, TrustedBiller.category == "electricity")
        .first()
    )
    if not elec:
        elec = TrustedBiller(
            id="10000000-0000-0000-0000-000000000001",
            household_id=hid,
            name="City Electricity",
            category="electricity",
            consumer_reference="ELEC-9988",
            status="active",
        )
        db.add(elec)
        db.flush()

    ins = (
        db.query(TrustedBiller)
        .filter(TrustedBiller.household_id == hid, TrustedBiller.category == "insurance")
        .first()
    )
    if not ins:
        ins = TrustedBiller(
            id="10000000-0000-0000-0000-000000000002",
            household_id=hid,
            name="Safe Insurance",
            category="insurance",
            consumer_reference="INS-4421",
            status="active",
        )
        db.add(ins)
        db.flush()

    if not db.query(ApprovedBeneficiary).filter(
        ApprovedBeneficiary.household_id == hid,
        ApprovedBeneficiary.account_number == "112233440101",
    ).first():
        db.add(
            ApprovedBeneficiary(
                id="20000000-0000-0000-0000-000000000001",
                household_id=hid,
                biller_id=elec.id,
                display_name="City Electricity Supply",
                account_number="112233440101",
                account_number_masked="••••••••0101",
                ifsc="HDFC0001234",
                status="active",
            )
        )

    if not db.query(ApprovedBeneficiary).filter(
        ApprovedBeneficiary.household_id == hid,
        ApprovedBeneficiary.account_number == "556677880202",
    ).first():
        db.add(
            ApprovedBeneficiary(
                id="20000000-0000-0000-0000-000000000002",
                household_id=hid,
                biller_id=ins.id,
                display_name="Safe Insurance Premium",
                account_number="556677880202",
                account_number_masked="••••••••0202",
                ifsc="ICIC0004321",
                status="active",
            )
        )

    db.commit()
