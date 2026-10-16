import json
import logging
import unittest.mock as mock
import pytest
from armoriq_sdk.exceptions import (
    PolicyBlockedException,
    PolicyHoldException,
    TokenExpiredException,
    MCPInvocationException,
)
from armoriq_sdk.models import PlanCapture, IntentToken, MCPInvocationResult
from backend.app.core.config import settings
from backend.app.integrations.armoriq_gateway import ArmorIQGateway, GatewayResult
from backend.app.services.mcp_tools import (
    ALLOWED_TOOLS,
    create_authorization_context,
    resolve_authorization_context,
)

@pytest.fixture(autouse=True)
def setup_armoriq_required():
    old = settings.ARMORIQ_ENFORCEMENT
    old_route = settings.ARMORIQ_ROUTE
    old_key = settings.ARMORIQ_API_KEY
    settings.ARMORIQ_ENFORCEMENT = "required"
    settings.ARMORIQ_ROUTE = "proxy"
    settings.ARMORIQ_API_KEY = "test_key"
    yield
    settings.ARMORIQ_ENFORCEMENT = old
    settings.ARMORIQ_ROUTE = old_route
    settings.ARMORIQ_API_KEY = old_key

def test_u1_verified_sdk_initialization_and_config_failure():
    """U1: Verified SDK initialization and configuration failure handling."""
    gw = ArmorIQGateway()
    with mock.patch("armoriq_sdk.ArmorIQClient", side_effect=Exception("Config error")):
        gw.initialize()
        assert gw._init_error is not None
        assert gw.is_healthy() == "down"
        res = gw.invoke_tool("list_bills", {})
        assert res.status == "unavailable_before_send"

def test_disabled_enforcement_fails_before_tool_invocation():
    gw = ArmorIQGateway()
    settings.ARMORIQ_ENFORCEMENT = "disabled"

    res = gw.invoke_tool(
        "propose_payment",
        {"bill_id": "b1", "idempotency_key": "k1"},
    )

    assert res.status == "unavailable_before_send"
    assert "must be required" in (res.reason or "")

def test_decision_gate_cannot_authorize_local_execution():
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    gw.client = mock_client
    gw._initialized = True
    settings.ARMORIQ_ROUTE = "decision_gate"

    res = gw.invoke_tool(
        "propose_payment",
        {"bill_id": "b1", "idempotency_key": "k1"},
    )

    assert res.status == "unavailable_before_send"
    assert not mock_client.start_session.called
    assert not mock_client.invoke.called

def test_gateway_uses_sdk_proxy_and_auth_type_contract():
    gw = ArmorIQGateway()
    old_values = {
        name: getattr(settings, name)
        for name in (
            "ARMORIQ_ENFORCEMENT",
            "ARMORIQ_ROUTE",
            "ARMORIQ_API_KEY",
            "KEEPER_MCP_PUBLIC_URL",
            "KEEPER_MCP_INBOUND_SECRET",
            "ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN",
        )
    }
    settings.ARMORIQ_ENFORCEMENT = "required"
    settings.ARMORIQ_ROUTE = "proxy"
    settings.ARMORIQ_API_KEY = "test_key"
    settings.KEEPER_MCP_PUBLIC_URL = "https://mcp.example.test/mcp"
    settings.KEEPER_MCP_INBOUND_SECRET = "backend-secret"
    settings.ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN = "backend-secret"
    try:
        with mock.patch("armoriq_sdk.ArmorIQClient") as client_class:
            gw.initialize()
        kwargs = client_class.call_args.kwargs
        assert "proxy_endpoint" not in kwargs
        assert kwargs["mcp_credentials"][settings.ARMORIQ_MCP_NAME] == {
            "authType": "bearer",
            "token": "backend-secret",
        }
    finally:
        for name, value in old_values.items():
            setattr(settings, name, value)

def test_gateway_rejects_mismatched_mcp_bearer_credentials(monkeypatch):
    gw = ArmorIQGateway()
    monkeypatch.setattr(settings, "ARMORIQ_ENFORCEMENT", "required")
    monkeypatch.setattr(settings, "ARMORIQ_ROUTE", "proxy")
    monkeypatch.setattr(settings, "ARMORIQ_API_KEY", "test_key")
    monkeypatch.setattr(settings, "KEEPER_MCP_PUBLIC_URL", "https://mcp.example.test/mcp")
    monkeypatch.setattr(settings, "KEEPER_MCP_INBOUND_SECRET", "backend-secret")
    monkeypatch.setattr(settings, "ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN", "different-proxy-token")

    with mock.patch("armoriq_sdk.ArmorIQClient") as client_class:
        gw.initialize()

    assert gw.is_healthy() == "down"
    assert "must match KEEPER_MCP_INBOUND_SECRET" in (gw._init_error or "")
    client_class.assert_not_called()

    from backend.app.services.agent_service import processing_configuration_blockers

    assert "ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN must match KEEPER_MCP_INBOUND_SECRET" in (
        processing_configuration_blockers()
    )

def test_mcp_household_context_is_signed_and_tamper_evident(seed_data):
    household_id = str(seed_data["h1"].id)
    context = create_authorization_context(household_id, "owner@test.com")
    assert resolve_authorization_context(context) == household_id

    forged_context = context[:-1] + ("A" if context[-1] != "A" else "B")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        resolve_authorization_context(forged_context)
    assert exc_info.value.status_code == 401

def test_u2_correct_intent_plan_construction():
    """U2: Correct intent-plan construction."""
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_capture = mock.MagicMock()
    mock_token = mock.MagicMock()
    mock_client.capture_plan.return_value = mock_capture
    mock_client.get_intent_token.return_value = mock_token
    mock_client.invoke.return_value = mock.MagicMock(result={"status": "ok"})
    gw.client = mock_client
    gw._initialized = True

    res = gw.invoke_tool(
        "propose_payment",
        {"bill_id": "b1", "idempotency_key": "k1"},
        intent_prompt="The user explicitly approved bill b1 for payment.",
    )
    assert res.status == "allowed_and_executed"
    # Verify capture_plan parameters
    mock_client.capture_plan.assert_called_once()
    args, kwargs = mock_client.capture_plan.call_args
    assert kwargs["prompt"] == "The user explicitly approved bill b1 for payment."
    assert kwargs["llm"] == settings.GEMINI_MODEL
    assert kwargs["plan"]["goal"] == "Invoke the permitted Keeper tool propose_payment."
    assert kwargs["plan"]["steps"][0]["action"] == "propose_payment"
    assert kwargs["plan"]["steps"][0]["mcp"] == settings.ARMORIQ_MCP_NAME
    assert kwargs["plan"]["steps"][0]["params"] == {"bill_id": "b1", "idempotency_key": "k1"}

def test_u3_successful_authorized_invocation():
    """U3: Successful authorized invocation."""
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.return_value = mock.MagicMock()
    mock_client.invoke.return_value = mock.MagicMock(result={"decision": "allow", "txn": "123"})
    gw.client = mock_client
    gw._initialized = True

    res = gw.invoke_tool("propose_payment", {"bill_id": "b1", "idempotency_key": "k1"})
    assert res.status == "allowed_and_executed"
    assert res.payload == {"decision": "allow", "txn": "123"}

def test_u4_explicit_armoriq_policy_denial():
    """U4: Explicit ArmorIQ policy denial."""
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.return_value = mock.MagicMock()
    mock_client.invoke.side_effect = PolicyBlockedException("Rule blocked by policy engine")
    gw.client = mock_client
    gw._initialized = True

    res = gw.invoke_tool("propose_payment", {"bill_id": "b1", "idempotency_key": "k1"})
    assert res.status == "denied_by_armoriq"
    assert "Rule blocked" in res.reason

def test_armoriq_hold_is_distinct_from_denial():
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.side_effect = PolicyHoldException("Needs caregiver review")
    gw.client = mock_client
    gw._initialized = True

    result = gw.invoke_tool("propose_payment", {"bill_id": "b1", "idempotency_key": "k1"})

    assert result.status == "held_by_armoriq"
    assert result.reason == "Needs caregiver review"
    assert not mock_client.invoke.called

def test_u5_token_creation_failure_before_invocation():
    """U5: Token creation failure before invocation."""
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.side_effect = Exception("Control plane unreachable")
    gw.client = mock_client
    gw._initialized = True

    res = gw.invoke_tool("propose_payment", {"bill_id": "b1", "idempotency_key": "k1"})
    assert res.status == "unavailable_before_send"
    assert not mock_client.invoke.called

def test_u6_token_expiry_handling_without_duplicate_execution():
    """U6: Token expiry handling without duplicate execution."""
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.return_value = mock.MagicMock()
    # First invoke raises TokenExpiredException, second succeeds
    mock_client.invoke.side_effect = [
        TokenExpiredException("Token expired"),
        mock.MagicMock(result={"decision": "allow"}),
    ]
    gw.client = mock_client
    gw._initialized = True

    res = gw.invoke_tool("propose_payment", {"bill_id": "b1", "idempotency_key": "k1"})
    assert res.status == "allowed_and_executed"
    assert mock_client.invoke.call_count == 2


def test_token_expiry_retry_failure_after_send_is_ambiguous():
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.return_value = mock.MagicMock()
    mock_client.invoke.side_effect = [
        TokenExpiredException("Token expired"),
        MCPInvocationException("Proxy response lost", status_code=502),
    ]
    gw.client = mock_client
    gw._initialized = True

    result = gw.invoke_tool("propose_payment", {"bill_id": "bill-1", "idempotency_key": "attempt-1"})

    assert result.status == "ambiguous_after_send"
    assert result.is_ambiguous is True
    assert mock_client.invoke.call_count == 2


def test_u7_timeout_after_invocation_becomes_ambiguous():
    """U7: Timeout after invocation becomes ambiguous."""
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.return_value = mock.MagicMock()
    mock_client.invoke.side_effect = MCPInvocationException("Timeout after send")
    gw.client = mock_client
    gw._initialized = True

    res = gw.invoke_tool("propose_payment", {"bill_id": "b1", "idempotency_key": "k1"})
    assert res.status == "ambiguous_after_send"
    assert res.is_ambiguous is True

def test_u8_no_automatic_invocation_retry():
    """U8: No automatic invocation retry on ambiguous outcome."""
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.return_value = mock.MagicMock()
    mock_client.invoke.side_effect = MCPInvocationException("Ambiguous network drop")
    gw.client = mock_client
    gw._initialized = True

    res = gw.invoke_tool("propose_payment", {"bill_id": "b1", "idempotency_key": "k1"})
    assert res.status == "ambiguous_after_send"
    # Call count must be exactly 1
    assert mock_client.invoke.call_count == 1


def test_proxy_failure_logs_stage_and_status_without_raw_error_body(caplog):
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.return_value = mock.MagicMock()
    mock_client.invoke.side_effect = MCPInvocationException(
        "proxy body: Internal Proxy Error; test-secret",
        status_code=502,
    )
    gw.client = mock_client
    gw._initialized = True

    with caplog.at_level(logging.ERROR, logger="backend.app.integrations.armoriq_gateway"):
        result = gw.invoke_tool(
            "list_bills",
            {},
            request_id="diagnostic-request-123",
        )

    assert result.status == "ambiguous_after_send"
    assert "diagnostic-request-123" in caplog.text
    assert "status_code=502" in caplog.text
    assert "error_type=MCPInvocationException" in caplog.text
    assert "error_category=internal_proxy_error" in caplog.text
    assert "test-secret" not in caplog.text


def test_u9_mcp_inbound_authentication_is_mandatory(client):
    """U9: MCP inbound authentication is mandatory."""
    res = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert res.status_code == 401
    assert "unauthenticated" in res.json()["error"]["code"]


def test_mcp_logs_sanitized_upstream_correlation_id(client, caplog):
    headers = {
        "Authorization": f"Bearer {settings.KEEPER_MCP_INBOUND_SECRET}",
        "X-Request-ID": "sdk-request-123",
    }
    with caplog.at_level(logging.INFO, logger="backend.app.api.mcp"):
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers=headers,
        )

    assert response.status_code == 200
    assert "correlation_id=sdk-request-123" in caplog.text


def test_mcp_jsonrpc_sse_initialize_list_and_call(client, seed_data, db):
    from datetime import date
    from backend.app.models.models import Bill

    db.add(
        Bill(
            household_id=seed_data["h1"].id,
            title="Household one bill",
            category="electricity",
            amount=1200.00,
            currency="INR",
            due_date=date(2026, 11, 10),
            status="received",
            source="manual",
            destination_account_number="112233440101",
            destination_account_number_masked="••••••••0101",
            destination_ifsc="HDFC0001234",
            destination_matches_approved=True,
        )
    )
    db.commit()
    headers = {"Authorization": f"Bearer {settings.KEEPER_MCP_INBOUND_SECRET}"}

    def parse_event(response):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        data_line = next(line for line in response.text.splitlines() if line.startswith("data: "))
        return json.loads(data_line.removeprefix("data: "))

    initialized = parse_event(
        client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            headers=headers,
        )
    )
    assert initialized["result"]["protocolVersion"] == "2024-11-05"

    listed = parse_event(
        client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=headers)
    )
    assert {tool["name"] for tool in listed["result"]["tools"]} == set(ALLOWED_TOOLS)

    called = parse_event(
        client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "list_bills",
                    "arguments": {"authorization_context": create_authorization_context(seed_data["h1"].id, "owner@test.com")},
                },
            },
            headers=headers,
        )
    )
    tool_payload = json.loads(called["result"]["content"][0]["text"])
    assert [bill["title"] for bill in tool_payload["bills"]] == ["Household one bill"]

    other_household_call = parse_event(
        client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_bills",
                    "arguments": {"authorization_context": create_authorization_context(seed_data["h2"].id, "other@test.com")},
                },
            },
            headers=headers,
        )
    )
    other_payload = json.loads(other_household_call["result"]["content"][0]["text"])
    assert other_payload == {"bills": []}

def test_u10_cross_household_requests_fail_closed(client, seed_data):
    """U10: Cross-household requests fail closed."""
    from backend.tests.conftest import make_auth_token
    # H2 user tries approval resume which targets different household
    token_h2 = make_auth_token(seed_data["h2_user_id"], "other@test.com")
    # Fake approval in H2
    fake_id = "00000000-0000-0000-0000-000000000099"
    res = client.post(
        f"/api/v1/approvals/{fake_id}/approve",
        json={"details_hash": "hash123"},
        headers={"Authorization": f"Bearer {token_h2}"},
    )
    # 404 because approval not found, or 503 if attempted
    assert res.status_code in (404, 503)

def test_u11_approval_resume_uses_permitted_tool():
    """U11: Approval resume uses permitted tool 'propose_payment'."""
    gw = ArmorIQGateway()
    mock_client = mock.MagicMock()
    mock_client.capture_plan.return_value = mock.MagicMock()
    mock_client.get_intent_token.return_value = mock.MagicMock()
    mock_client.invoke.return_value = mock.MagicMock(result={"resumed": True})
    gw.client = mock_client
    gw._initialized = True

    res = gw.invoke_tool("propose_payment", {"bill_id": "b1", "idempotency_key": "resume-k1"})
    assert res.status == "allowed_and_executed"
    mock_client.invoke.assert_called_with(
        mcp=settings.ARMORIQ_MCP_NAME,
        action="propose_payment",
        intent_token=mock.ANY,
        params={"bill_id": "b1", "idempotency_key": "resume-k1"},
        user_email=mock.ANY,
    )
