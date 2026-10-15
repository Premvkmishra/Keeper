from types import SimpleNamespace

from google.genai import types

from backend.app.core import config
from backend.app.integrations.armoriq_gateway import GatewayResult
from backend.app.services.agent_service import AgentService


def test_approved_bill_is_scoped_and_user_intent_reaches_armoriq(
    db, monkeypatch
):
    import google.genai

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "test-gemini-key")
    approved_bill_id = "approved-bill-id"
    intent = "I approved this exact bill; process only this payment."

    def function_call(name, args):
        return SimpleNamespace(
            function_calls=[SimpleNamespace(name=name, args=args)],
            candidates=[
                SimpleNamespace(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=f"request {name}")],
                    )
                )
            ],
            text=None,
        )

    responses = [
        function_call("get_bill", {"bill_id": approved_bill_id}),
        function_call(
            "propose_payment",
            {"bill_id": approved_bill_id, "idempotency_key": "model-chosen-key"},
        ),
        SimpleNamespace(function_calls=[], candidates=[], text="Payment processing completed."),
    ]

    class FakeModels:
        def generate_content(self, **_kwargs):
            return responses.pop(0)

    class FakeClient:
        def __init__(self, **_kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(google.genai, "Client", FakeClient)

    calls = []

    def invoke_tool(name, params, **kwargs):
        calls.append((name, params, kwargs))
        result = {"id": approved_bill_id} if name == "get_bill" else {"attempt": {"status": "succeeded"}}
        return GatewayResult(status="allowed_and_executed", payload=result)

    from backend.app.services import agent_service

    monkeypatch.setattr(agent_service.armoriq_gateway, "invoke_tool", invoke_tool)

    result = AgentService().chat(
        db=db,
        household_id="household-id",
        user_email="owner@example.test",
        message=intent,
        approved_bill_id=approved_bill_id,
        idempotency_key="approval-idempotency-key",
    )

    assert [name for name, _params, _kwargs in calls] == ["get_bill", "propose_payment"]
    assert calls[0][1]["bill_id"] == approved_bill_id
    assert calls[1][1]["bill_id"] == approved_bill_id
    assert calls[1][1]["idempotency_key"] == "approval-idempotency-key"
    assert all(call[1]["authorization_context"] for call in calls)
    assert all(call[2]["intent_prompt"] == intent for call in calls)
    assert result["tool_trace"][-1]["result"]["attempt"]["status"] == "succeeded"


def test_household_bootstrap_creates_owner_and_is_idempotent(client, db):
    import uuid

    from backend.app.models.models import HouseholdMember, HouseholdPolicy
    from backend.tests.conftest import make_auth_token

    user_id = str(uuid.uuid4())
    email = "new-owner@example.test"
    token = make_auth_token(user_id, email)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"display_name": "New Owner", "household_name": "My Home"}

    first = client.post("/api/v1/auth/household", json=payload, headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body["email"] == email
    assert body["role"] == "owner"
    assert body["household"]["name"] == "My Home"

    member = db.query(HouseholdMember).filter(HouseholdMember.user_id == user_id).one()
    policy = db.query(HouseholdPolicy).filter(HouseholdPolicy.household_id == member.household_id).one()
    assert member.display_name == "New Owner"
    assert policy.auto_pay_limit == 10000.00

    second = client.post(
        "/api/v1/auth/household",
        json={"display_name": "Changed Name", "household_name": "Changed Home"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["household"]["id"] == body["household"]["id"]
    assert second.json()["household"]["name"] == "My Home"


def test_household_bootstrap_rejects_missing_authentication(client):
    response = client.post(
        "/api/v1/auth/household",
        json={"display_name": "New Owner", "household_name": "My Home"},
    )
    assert response.status_code == 401
