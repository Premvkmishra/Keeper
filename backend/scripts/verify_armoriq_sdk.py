#!/usr/bin/env python3
"""
Verification script for armoriq-sdk == 0.6.10.
Validates the presence of required classes, signatures, and exception types.
"""
import inspect
import sys

def verify_armoriq_sdk():
    print("[1/5] Checking armoriq_sdk package import and version...")
    try:
        import armoriq_sdk
        version = getattr(armoriq_sdk, "__version__", getattr(armoriq_sdk, "VERSION", "unknown"))
        print(f"      Imported armoriq_sdk version: {version}")
        assert version == "0.6.10", f"Expected version 0.6.10, got {version}"
    except ImportError as e:
        print(f"FAILED: Cannot import armoriq_sdk: {e}", file=sys.stderr)
        sys.exit(1)

    print("[2/5] Checking ArmorIQClient and methods...")
    try:
        from armoriq_sdk import ArmorIQClient
        # Check constructor parameters
        sig_init = inspect.signature(ArmorIQClient.__init__)
        params = sig_init.parameters
        required_params = ["api_key", "timeout", "max_retries", "mcp_credentials"]
        for p in required_params:
            assert p in params, f"ArmorIQClient.__init__ missing parameter: {p}"

        # Check required methods
        assert hasattr(ArmorIQClient, "capture_plan"), "ArmorIQClient missing capture_plan"
        assert hasattr(ArmorIQClient, "get_intent_token"), "ArmorIQClient missing get_intent_token"
        assert hasattr(ArmorIQClient, "invoke"), "ArmorIQClient missing invoke"
        assert hasattr(ArmorIQClient, "close"), "ArmorIQClient missing close"

        sig_invoke = inspect.signature(ArmorIQClient.invoke)
        invoke_params = sig_invoke.parameters
        assert "mcp" in invoke_params, "invoke missing 'mcp'"
        assert "action" in invoke_params, "invoke missing 'action'"
        assert "intent_token" in invoke_params, "invoke missing 'intent_token'"
        assert "params" in invoke_params, "invoke missing 'params'"
        assert "user_email" in invoke_params, "invoke missing 'user_email'"
        print("      ArmorIQClient methods and signatures verified.")
    except Exception as e:
        print(f"FAILED: ArmorIQClient verification error: {e}", file=sys.stderr)
        sys.exit(1)

    print("[3/5] Checking ArmorIQSession and decision gate fallback...")
    try:
        from armoriq_sdk import ArmorIQSession
        assert hasattr(ArmorIQSession, "check"), "ArmorIQSession missing check"
        sig_check = inspect.signature(ArmorIQSession.check)
        check_params = sig_check.parameters
        assert "tool_name" in check_params, "check missing 'tool_name'"
        assert "tool_args" in check_params, "check missing 'tool_args'"
        print("      ArmorIQSession.check signature verified.")
    except Exception as e:
        print(f"FAILED: ArmorIQSession verification error: {e}", file=sys.stderr)
        sys.exit(1)

    print("[4/5] Checking Exception classes...")
    try:
        from armoriq_sdk.exceptions import (
            ArmorIQException,
            PolicyBlockedException,
            PolicyHoldException,
            InvalidTokenException,
            IntentMismatchException,
            DelegationException,
            TokenExpiredException,
            ConfigurationException,
            MCPInvocationException,
        )
        print("      All required exception classes verified.")
    except ImportError as e:
        print(f"FAILED: Missing expected exception class: {e}", file=sys.stderr)
        sys.exit(1)

    print("[5/5] Checking Models...")
    try:
        from armoriq_sdk.models import PlanCapture, IntentToken, MCPInvocationResult
        assert "plan" in PlanCapture.model_fields
        assert "token_id" in IntentToken.model_fields
        assert "result" in MCPInvocationResult.model_fields
        assert "status" in MCPInvocationResult.model_fields
        print("      Models PlanCapture, IntentToken, MCPInvocationResult verified.")
    except Exception as e:
        print(f"FAILED: Model verification error: {e}", file=sys.stderr)
        sys.exit(1)

    print("\nSUCCESS: armoriq-sdk 0.6.10 verified successfully.")

if __name__ == "__main__":
    verify_armoriq_sdk()
