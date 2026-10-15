import hmac
import logging
import secrets
import threading
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Error classification outcomes
GatewayOutcomeStatus = Literal[
    "allowed_and_executed",
    "denied_by_armoriq",
    "held_by_armoriq",
    "unavailable_before_send",
    "ambiguous_after_send",
]

class GatewayResult:
    def __init__(
        self,
        status: GatewayOutcomeStatus,
        payload: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        is_ambiguous: bool = False,
    ):
        self.status = status
        self.payload = payload
        self.reason = reason
        self.is_ambiguous = is_ambiguous

class ArmorIQGateway:
    def __init__(self):
        self.client = None
        self._initialized = False
        self._init_error = None
        self._lock = threading.Lock()

    def initialize(self):
        with self._lock:
            if self._initialized:
                return
            if settings.ARMORIQ_ENFORCEMENT.lower() != "required":
                self._init_error = "ARMORIQ_ENFORCEMENT must be required for tool execution."
                logger.error(self._init_error)
                return
            if settings.ARMORIQ_ROUTE != "proxy":
                self._init_error = "ARMORIQ_ROUTE must be proxy for enforced tool execution."
                logger.error(self._init_error)
                return
            missing = [
                name
                for name, value in (
                    ("ARMORIQ_API_KEY", settings.ARMORIQ_API_KEY),
                    ("KEEPER_MCP_PUBLIC_URL", settings.KEEPER_MCP_PUBLIC_URL),
                    ("KEEPER_MCP_INBOUND_SECRET", settings.KEEPER_MCP_INBOUND_SECRET),
                )
                if not value
            ]
            if missing:
                self._init_error = "Missing required ArmorIQ configuration: " + ", ".join(missing)
                logger.error(self._init_error)
                return

            try:
                from armoriq_sdk import ArmorIQClient
                # Setup credentials map for MCP bearer token
                mcp_creds = {}
                token_to_use = (
                    settings.ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN
                    or settings.KEEPER_MCP_INBOUND_SECRET
                )
                if token_to_use:
                    mcp_creds[settings.ARMORIQ_MCP_NAME] = {
                        "authType": settings.ARMORIQ_MCP_KEEPER_PAYMENTS_AUTH_TYPE,
                        "token": token_to_use,
                    }

                # Construct client with verified parameters
                self.client = ArmorIQClient(
                    api_key=settings.ARMORIQ_API_KEY,
                    timeout=15.0,
                    max_retries=0,
                    mcp_credentials=mcp_creds if mcp_creds else None,
                )
                self._initialized = True
                logger.info("ArmorIQClient successfully initialized.")
            except Exception as e:
                self._init_error = str(e)
                logger.error(f"Failed to initialize ArmorIQClient: {e}")

    def close(self):
        with self._lock:
            if self.client and hasattr(self.client, "close"):
                try:
                    self.client.close()
                except Exception as e:
                    logger.warning(f"Error closing ArmorIQClient: {e}")
            self.client = None
            self._initialized = False

    def is_healthy(self) -> str:
        """Returns 'ok', 'down', or 'unconfigured'."""
        if settings.ARMORIQ_ENFORCEMENT == "disabled":
            return "unconfigured"
        if not settings.ARMORIQ_API_KEY:
            return "unconfigured"
        if not self._initialized or self._init_error:
            return "down"
        return "ok"

    def invoke_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        user_email: str = "agent@keeper.internal",
    ) -> GatewayResult:
        """
        Executes an agent tool invocation governed by ArmorIQ.
        Distinguishes four outcomes:
        - allowed_and_executed(payload)
        - denied_by_armoriq(reason)
        - unavailable_before_send
        - ambiguous_after_send
        """
        if settings.ARMORIQ_ENFORCEMENT.lower() != "required":
            return GatewayResult(
                status="unavailable_before_send",
                reason="ARMORIQ_ENFORCEMENT must be required; no tool was sent.",
            )

        if settings.ARMORIQ_ROUTE != "proxy":
            return GatewayResult(
                status="unavailable_before_send",
                reason="ARMORIQ_ROUTE must be proxy; decision-gate checks cannot authorize local execution.",
            )

        if not self._initialized:
            self.initialize()

        if self._init_error or not self.client:
            return GatewayResult(
                status="unavailable_before_send",
                reason=f"ArmorIQ initialization failed: {self._init_error or 'client not created'}",
            )

        from armoriq_sdk.exceptions import (
            PolicyBlockedException,
            PolicyHoldException,
            InvalidTokenException,
            IntentMismatchException,
            DelegationException,
            TokenExpiredException,
            MCPInvocationException,
        )

        # Proxy Route Flow
        intent_token = None
        try:
            # 1. Capture Intent Plan
            plan_capture = self.client.capture_plan(
                llm="keeper-agent-v1",
                prompt=f"Execute tool {tool_name} with parameters",
                plan={
                    "goal": f"Invoke the permitted Keeper tool {tool_name}.",
                    "steps": [
                        {
                            "action": tool_name,
                            "mcp": settings.ARMORIQ_MCP_NAME,
                            "params": params,
                        }
                    ]
                },
            )

            # 2. Request Intent Token (validity 60 seconds)
            intent_token = self.client.get_intent_token(
                plan_capture=plan_capture,
                validity_seconds=60.0,
            )
        except PolicyHoldException as e:
            return GatewayResult(status="held_by_armoriq", reason=str(e))
        except (PolicyBlockedException, InvalidTokenException, IntentMismatchException, DelegationException) as e:
            return GatewayResult(status="denied_by_armoriq", reason=f"Intent creation denied: {str(e)}")
        except Exception as e:
            logger.error(f"Intent token creation failure before send: {e}")
            return GatewayResult(status="unavailable_before_send", reason=f"Failed before invocation: {str(e)}")

        # 3. Authorized Tool Invocation via ArmorIQ Proxy
        try:
            invocation_result = self.client.invoke(
                mcp=settings.ARMORIQ_MCP_NAME,
                action=tool_name,
                intent_token=intent_token,
                params=params,
                user_email=user_email,
            )
            # Unpack result
            res_dict = invocation_result.result if hasattr(invocation_result, "result") else invocation_result
            return GatewayResult(status="allowed_and_executed", payload=res_dict)
        except TokenExpiredException:
            # Token expired client-side before send: remint once safely
            try:
                plan_capture = self.client.capture_plan(
                    llm="keeper-agent-v1",
                    prompt=f"Execute tool {tool_name} with parameters",
                    plan={
                        "goal": f"Invoke the permitted Keeper tool {tool_name}.",
                        "steps": [{"action": tool_name, "mcp": settings.ARMORIQ_MCP_NAME, "params": params}],
                    },
                )
                intent_token = self.client.get_intent_token(plan_capture=plan_capture, validity_seconds=60.0)
                invocation_result = self.client.invoke(
                    mcp=settings.ARMORIQ_MCP_NAME,
                    action=tool_name,
                    intent_token=intent_token,
                    params=params,
                    user_email=user_email,
                )
                res_dict = invocation_result.result if hasattr(invocation_result, "result") else invocation_result
                return GatewayResult(status="allowed_and_executed", payload=res_dict)
            except PolicyHoldException as e:
                return GatewayResult(status="held_by_armoriq", reason=str(e))
            except (PolicyBlockedException, InvalidTokenException, IntentMismatchException, DelegationException) as e:
                return GatewayResult(status="denied_by_armoriq", reason=str(e))
            except Exception as e:
                return GatewayResult(status="unavailable_before_send", reason=f"Intent remint failed before invocation: {str(e)}")
        except PolicyHoldException as e:
            return GatewayResult(status="held_by_armoriq", reason=str(e))
        except (PolicyBlockedException, InvalidTokenException, IntentMismatchException, DelegationException) as e:
            return GatewayResult(status="denied_by_armoriq", reason=str(e))
        except MCPInvocationException as e:
            # Invocation exception after send -> classified as ambiguous
            logger.error(f"MCP Invocation error after send: {e}")
            return GatewayResult(status="ambiguous_after_send", reason=str(e), is_ambiguous=True)
        except Exception as e:
            # Network drop / timeout after send -> ambiguous
            logger.error(f"Network drop / timeout after tool invocation: {e}")
            return GatewayResult(status="ambiguous_after_send", reason=str(e), is_ambiguous=True)

    @staticmethod
    def verify_inbound_secret(auth_header: Optional[str]) -> bool:
        """Constant-time comparison for MCP endpoint inbound token."""
        secret = settings.KEEPER_MCP_INBOUND_SECRET
        if not secret:
            # If no secret configured, reject all incoming requests
            return False
        if not auth_header or not auth_header.startswith("Bearer "):
            return False
        token = auth_header.split(" ", 1)[1].strip()
        return secrets.compare_digest(token, secret)

armoriq_gateway = ArmorIQGateway()
