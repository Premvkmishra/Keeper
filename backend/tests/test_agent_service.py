from types import SimpleNamespace

import pytest
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
    assert all(call[2]["model_name"] == config.settings.GEMINI_MODEL for call in calls)
    assert result["tool_trace"][-1]["result"]["attempt"]["status"] == "succeeded"


def test_gemini_retries_transient_service_unavailable(db, monkeypatch):
    import google.genai
    from google.genai.errors import ServerError

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr("backend.app.services.agent_service.time.sleep", lambda _seconds: None)

    class FakeModels:
        calls = 0

        def generate_content(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ServerError(
                    503,
                    {
                        "error": {
                            "code": 503,
                            "status": "UNAVAILABLE",
                            "message": "Temporary high demand",
                        }
                    },
                )
            return SimpleNamespace(function_calls=[], candidates=[], text="Read-only response.")

    models = FakeModels()

    class FakeClient:
        def __init__(self, **_kwargs):
            self.models = models

    monkeypatch.setattr(google.genai, "Client", FakeClient)
    result = AgentService().chat(
        db=db,
        household_id="household-id",
        user_email="owner@example.test",
        message="List bills.",
    )

    assert models.calls == 2
    assert result["reply"] == "Read-only response."
    assert result["tool_trace"] == []


def test_gemini_falls_back_to_next_model_and_uses_it_for_tool_authorization(
    db, monkeypatch
):
    import google.genai
    from google.genai.errors import ServerError

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(config.settings, "GEMINI_MODEL", "gemini-primary")
    monkeypatch.setattr(config.settings, "GEMINI_FALLBACK_MODELS", "gemini-fallback,gemini-last")
    monkeypatch.setattr("backend.app.services.agent_service.time.sleep", lambda _seconds: None)

    def unavailable():
        return ServerError(
            503,
            {
                "error": {
                    "code": 503,
                    "status": "UNAVAILABLE",
                    "message": "Temporary high demand",
                }
            },
        )

    models_called = []

    class FakeModels:
        def generate_content(self, **kwargs):
            models_called.append(kwargs["model"])
            if kwargs["model"] == "gemini-primary":
                raise unavailable()
            if len(models_called) == 4:
                return SimpleNamespace(
                    function_calls=[SimpleNamespace(name="list_bills", args={})],
                    candidates=[
                        SimpleNamespace(
                            content=types.Content(
                                role="model",
                                parts=[types.Part.from_text(text="request list_bills")],
                            )
                        )
                    ],
                    text=None,
                )
            return SimpleNamespace(function_calls=[], candidates=[], text="Bills loaded.")

    class FakeClient:
        def __init__(self, **_kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(google.genai, "Client", FakeClient)

    from backend.app.services import agent_service

    invoked_models = []

    def invoke_tool(_name, _params, **kwargs):
        invoked_models.append(kwargs["model_name"])
        return GatewayResult(status="allowed_and_executed", payload={"bills": []})

    monkeypatch.setattr(agent_service.armoriq_gateway, "invoke_tool", invoke_tool)
    result = AgentService().chat(
        db=db,
        household_id="household-id",
        user_email="owner@example.test",
        message="List bills.",
    )

    assert models_called == ["gemini-primary"] * 3 + ["gemini-fallback", "gemini-fallback"]
    assert invoked_models == ["gemini-fallback"]
    assert result["model"] == "gemini-fallback"
    assert result["reply"] == "Bills loaded."


def test_gemini_exhausted_transient_retries_returns_provider_status(db, monkeypatch):
    import google.genai
    from fastapi import HTTPException
    from google.genai.errors import ServerError

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(config.settings, "GEMINI_MODEL", "gemini-primary")
    monkeypatch.setattr(config.settings, "GEMINI_FALLBACK_MODELS", "gemini-fallback,gemini-last")
    monkeypatch.setattr("backend.app.services.agent_service.time.sleep", lambda _seconds: None)

    models_called = []

    class FakeModels:
        def generate_content(self, **kwargs):
            models_called.append(kwargs["model"])
            raise ServerError(
                503,
                {
                    "error": {
                        "code": 503,
                        "status": "UNAVAILABLE",
                        "message": "Temporary high demand",
                    }
                },
            )

    models = FakeModels()

    class FakeClient:
        def __init__(self, **_kwargs):
            self.models = models

    monkeypatch.setattr(google.genai, "Client", FakeClient)
    with pytest.raises(HTTPException) as exc_info:
        AgentService().chat(
            db=db,
            household_id="household-id",
            user_email="owner@example.test",
            message="List bills.",
        )

    assert models_called == ["gemini-primary"] * 3 + ["gemini-fallback", "gemini-last"]
    assert exc_info.value.status_code == 503
    assert "HTTP 503" in exc_info.value.detail["message"]


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
