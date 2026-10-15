import os
import pytest
from backend.app.core.config import settings

def _get_missing_live_prerequisite():
    if not settings.ARMORIQ_API_KEY:
        return "BLOCKED: ARMORIQ_API_KEY is not configured in local environment."
    if not settings.KEEPER_MCP_PUBLIC_URL:
        return "BLOCKED: KEEPER_MCP_PUBLIC_URL is not configured (public HTTPS MCP endpoint required)."
    if not settings.KEEPER_MCP_INBOUND_SECRET:
        return "BLOCKED: KEEPER_MCP_INBOUND_SECRET is not configured."
    return None

def test_l1_client_initialization():
    """L1: Actual ArmorIQ client initialization with verified live credentials."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)

    from armoriq_sdk import ArmorIQClient
    client = ArmorIQClient(api_key=settings.ARMORIQ_API_KEY, timeout=15.0, max_retries=0)
    assert client is not None
    client.close()

def test_l2_mcp_registration_and_connectivity():
    """L2: MCP registration and connectivity via ArmorIQ control plane."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)

    from armoriq_sdk import ArmorIQClient
    client = ArmorIQClient(api_key=settings.ARMORIQ_API_KEY)
    mcps = client.list_mcps()
    client.close()
    assert any(m.get("name") == settings.ARMORIQ_MCP_NAME for m in mcps)

def test_l3_authentication_credential_delivery():
    """L3: Authentication credential delivery to proxy."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)
    pytest.skip("BLOCKED: Awaiting live MCP proxy deployment confirmation.")

def test_l4_allowed_tool_invocation():
    """L4: Allowed tool invocation through ArmorIQ proxy."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)
    pytest.skip("BLOCKED: Awaiting live MCP proxy deployment confirmation.")

def test_l5_denied_tool_invocation():
    """L5: Denied tool invocation through ArmorIQ proxy."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)
    pytest.skip("BLOCKED: Awaiting live MCP proxy deployment confirmation.")

def test_l6_intent_token_mismatch_behavior():
    """L6: Intent/token mismatch behavior."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)
    pytest.skip("BLOCKED: Awaiting live MCP proxy deployment confirmation.")

def test_l7_approval_resume_through_proxy():
    """L7: Approval resume through the proxy."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)
    pytest.skip("BLOCKED: Awaiting live MCP proxy deployment confirmation.")

def test_l8_timeout_and_reconciliation_behavior():
    """L8: Timeout and reconciliation behavior."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)
    pytest.skip("BLOCKED: Awaiting live MCP proxy deployment confirmation.")

def test_spike_s1_decision_gate():
    """Spike S1: Verify whether configured decision-gate produces explicit allow/deny without executing MCP tool."""
    prereq = _get_missing_live_prerequisite()
    if prereq:
        pytest.skip(prereq)

    from armoriq_sdk import ArmorIQClient, ArmorIQSession
    client = ArmorIQClient(api_key=settings.ARMORIQ_API_KEY)
    session = client.start_session()
    assert hasattr(session, "check")
    session.close()
    client.close()
