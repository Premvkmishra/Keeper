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


def test_groq_tool_call_uses_armoriq_and_returns_followup_response(db, monkeypatch):
    import groq

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(config.settings, "GROQ_MODEL", "openai/gpt-oss-20b")

    responses = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call-1",
                                function=SimpleNamespace(name="list_bills", arguments="{}"),
                            )
                        ],
                    )
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="There are no bills.", tool_calls=[])
                )
            ]
        ),
    ]
    requests = []

    class FakeCompletions:
        def create(self, **kwargs):
            requests.append(kwargs)
            return responses.pop(0)

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(groq, "Groq", FakeClient)

    from backend.app.services import agent_service

    calls = []

    def invoke_tool(name, params, **kwargs):
        calls.append((name, params, kwargs))
        return GatewayResult(status="allowed_and_executed", payload={"bills": []})

    monkeypatch.setattr(agent_service.armoriq_gateway, "invoke_tool", invoke_tool)
    result = AgentService().chat(
        db=db,
        household_id="household-id",
        user_email="owner@example.test",
        message="List bills.",
    )

    assert result["reply"] == "There are no bills."
    assert result["model"] == "openai/gpt-oss-20b"
    assert calls[0][0] == "list_bills"
    assert calls[0][1]["authorization_context"]
    assert calls[0][2]["model_name"] == "openai/gpt-oss-20b"
    assert requests[1]["messages"][-1]["role"] == "tool"


def test_groq_stops_after_ambiguous_tool_result(db, monkeypatch):
    import groq

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(config.settings, "GROQ_MODEL", "openai/gpt-oss-20b")
    responses = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                id="call-ambiguous",
                                function=SimpleNamespace(name="list_bills", arguments="{}"),
                            )
                        ],
                    )
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Retrying the tool.", tool_calls=[])
                )
            ]
        ),
    ]
    completion_calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            completion_calls.append(kwargs)
            return responses.pop(0)

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(groq, "Groq", FakeClient)

    from backend.app.services import agent_service

    invocations = []

    def invoke_tool(name, _params, **_kwargs):
        invocations.append(name)
        return GatewayResult(
            status="ambiguous_after_send",
            reason="ArmorIQ proxy returned an indeterminate response.",
            is_ambiguous=True,
        )

    monkeypatch.setattr(agent_service.armoriq_gateway, "invoke_tool", invoke_tool)
    result = AgentService().chat(
        db=db,
        household_id="household-id",
        user_email="owner@example.test",
        message="List bills.",
    )

    assert len(completion_calls) == 1
    assert invocations == ["list_bills"]
    assert len(result["tool_trace"]) == 1
    assert "stopped further tool calls" in result["reply"]


def test_gemini_stops_after_ambiguous_tool_result(db, monkeypatch):
    import google.genai

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config.settings, "GEMINI_API_KEY", "test-gemini-key")
    responses = [
        SimpleNamespace(
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
        ),
        SimpleNamespace(function_calls=[], candidates=[], text="Retrying the tool."),
    ]
    model_calls = []

    class FakeModels:
        def generate_content(self, **_kwargs):
            model_calls.append(True)
            return responses.pop(0)

    class FakeClient:
        def __init__(self, **_kwargs):
            self.models = FakeModels()

    monkeypatch.setattr(google.genai, "Client", FakeClient)

    from backend.app.services import agent_service

    invocations = []

    def invoke_tool(name, _params, **_kwargs):
        invocations.append(name)
        return GatewayResult(
            status="ambiguous_after_send",
            reason="ArmorIQ proxy returned an indeterminate response.",
            is_ambiguous=True,
        )

    monkeypatch.setattr(agent_service.armoriq_gateway, "invoke_tool", invoke_tool)
    result = AgentService().chat(
        db=db,
        household_id="household-id",
        user_email="owner@example.test",
        message="List bills.",
    )

    assert len(model_calls) == 1
    assert invocations == ["list_bills"]
    assert len(result["tool_trace"]) == 1
    assert "stopped further tool calls" in result["reply"]


def test_groq_falls_back_after_model_not_found(db, monkeypatch):
    import groq

    monkeypatch.setattr(config.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config.settings, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(config.settings, "GROQ_MODEL", "groq-primary")
    monkeypatch.setattr(config.settings, "GROQ_FALLBACK_MODELS", "groq-fallback")

    models_called = []

    class NotFoundError(Exception):
        status_code = 404

    class FakeCompletions:
        def create(self, **kwargs):
            models_called.append(kwargs["model"])
            if kwargs["model"] == "groq-primary":
                raise NotFoundError("model not found")
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="Read-only response.", tool_calls=[])
                    )
                ]
            )

    class FakeClient:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(groq, "Groq", FakeClient)
    result = AgentService().chat(
        db=db,
        household_id="household-id",
        user_email="owner@example.test",
        message="List bills.",
    )

    assert models_called == ["groq-primary", "groq-fallback"]
    assert result["model"] == "groq-fallback"
    assert result["reply"] == "Read-only response."


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
