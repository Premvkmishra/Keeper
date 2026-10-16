import hmac
import logging
import secrets
import threading
import time
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel
from urllib.parse import urlsplit

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def _proxy_error_category(error: BaseException) -> str:
    message = str(error).lower()
    if "internal proxy error" in message:
        return "internal_proxy_error"
    if "timeout" in message or "timed out" in message:
        return "timeout"
    if "connection" in message:
        return "connection_error"
    return "proxy_invocation_error"


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
            self._init_error = None
            if settings.ARMORIQ_ENFORCEMENT.lower() != "required":
                self._init_error = "ARMORIQ_ENFORCEMENT must be required for tool execution."
                logger.error(self._init_error)
                return
            if settings.ARMORIQ_ROUTE != "proxy":
                self._init_error = "ARMORIQ_ROUTE must be proxy for enforced tool execution."
                logger.error(self._init_error)
                return
            if not settings.armoriq_mcp_credentials_match:
                self._init_error = (
                    "ARMORIQ_MCP_KEEPER_PAYMENTS_TOKEN must match "
                    "KEEPER_MCP_INBOUND_SECRET."
                )
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
                token_to_use = settings.KEEPER_MCP_INBOUND_SECRET
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
                logger.info(
                    "ArmorIQ client initialized enforcement=%s route=%s mcp=%s mcp_host=%s "
                    "api_key_configured=%s mcp_url_configured=%s inbound_secret_configured=%s "
                    "proxy_credentials_match=%s",
                    settings.ARMORIQ_ENFORCEMENT.lower(),
                    settings.ARMORIQ_ROUTE,
                    settings.ARMORIQ_MCP_NAME,
                    urlsplit(settings.KEEPER_MCP_PUBLIC_URL).hostname or "invalid",
                    bool(settings.ARMORIQ_API_KEY),
                    bool(settings.KEEPER_MCP_PUBLIC_URL),
                    bool(settings.KEEPER_MCP_INBOUND_SECRET),
                    settings.armoriq_mcp_credentials_match,
                )
            except Exception as e:
                self._init_error = f"ArmorIQ client initialization failed ({type(e).__name__})."
                logger.error("Failed to initialize ArmorIQClient error_type=%s", type(e).__name__)

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
        if not settings.armoriq_mcp_credentials_match:
            return "down"
        if not self._initialized or self._init_error:
            return "down"
        return "ok"

    def invoke_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        user_email: str = "agent@keeper.internal",
        intent_prompt: Optional[str] = None,
        request_id: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> GatewayResult:
        """
        Executes an agent tool invocation governed by ArmorIQ.
        Distinguishes four outcomes:
        - allowed_and_executed(payload)
        - denied_by_armoriq(reason)
        - unavailable_before_send
        - ambiguous_after_send
        """
        request_id = request_id or "untracked"
        model_name = model_name or settings.GEMINI_MODEL
        invocation_started_at = time.monotonic()
        logger.info(
            "ArmorIQ tool invocation started request_id=%s mcp=%s action=%s model=%s",
            request_id,
            settings.ARMORIQ_MCP_NAME,
            tool_name,
            model_name,
        )
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
            logger.info(
                "ArmorIQ plan capture started request_id=%s action=%s",
                request_id,
                tool_name,
            )
            # 1. Capture Intent Plan
            plan_capture = self.client.capture_plan(
                llm=model_name,
                prompt=(intent_prompt or f"Execute tool {tool_name} with parameters")[:4000],
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
            logger.info(
                "ArmorIQ intent token request started request_id=%s action=%s",
                request_id,
                tool_name,
            )
            intent_token = self.client.get_intent_token(
                plan_capture=plan_capture,
                validity_seconds=60.0,
            )
            logger.info(
                "ArmorIQ authorization ready request_id=%s action=%s",
                request_id,
                tool_name,
            )
        except PolicyHoldException as e:
            logger.warning(
                "ArmorIQ policy hold request_id=%s action=%s stage=authorization",
                request_id,
                tool_name,
            )
            return GatewayResult(status="held_by_armoriq", reason=str(e))
        except (PolicyBlockedException, InvalidTokenException, IntentMismatchException, DelegationException) as e:
            logger.warning(
                "ArmorIQ authorization denied request_id=%s action=%s error_type=%s",
                request_id,
                tool_name,
                type(e).__name__,
            )
            return GatewayResult(status="denied_by_armoriq", reason=f"Intent creation denied: {str(e)}")
        except Exception as e:
            logger.error(
                "ArmorIQ authorization failed before invocation request_id=%s action=%s "
                "error_type=%s status_code=%s",
                request_id,
                tool_name,
                type(e).__name__,
                getattr(e, "status_code", None),
            )
            return GatewayResult(
                status="unavailable_before_send",
                reason=(
                    "ArmorIQ authorization failed before invocation "
                    f"({type(e).__name__}, HTTP {getattr(e, 'status_code', None)})."
                ),
            )

        # 3. Authorized Tool Invocation via ArmorIQ Proxy
        try:
            logger.info(
                "ArmorIQ proxy invocation started request_id=%s mcp=%s action=%s",
                request_id,
                settings.ARMORIQ_MCP_NAME,
                tool_name,
            )
            invocation_result = self.client.invoke(
                mcp=settings.ARMORIQ_MCP_NAME,
                action=tool_name,
                intent_token=intent_token,
                params=params,
                user_email=user_email,
            )
            result_status = getattr(invocation_result, "status", "success")
            if not isinstance(result_status, str):
                result_status = "success"
            verified = getattr(invocation_result, "verified", True)
            if not isinstance(verified, bool):
                verified = True
            res_dict = invocation_result.result if hasattr(invocation_result, "result") else invocation_result
            if result_status != "success" or not verified:
                elapsed_ms = round((time.monotonic() - invocation_started_at) * 1000)
                logger.error(
                    "ArmorIQ proxy returned non-success request_id=%s action=%s sdk_status=%s "
                    "verified=%s duration_ms=%d outcome=ambiguous_after_send",
                    request_id,
                    tool_name,
                    result_status,
                    verified,
                    elapsed_ms,
                )
                return GatewayResult(
                    status="ambiguous_after_send",
                    reason=f"ArmorIQ invocation returned status={result_status}; execution could not be confirmed.",
                    is_ambiguous=True,
                )
            mcp_is_error = isinstance(res_dict, dict) and bool(res_dict.get("isError"))
            logger.info(
                "ArmorIQ proxy invocation completed request_id=%s action=%s sdk_status=%s "
                "verified=%s mcp_is_error=%s duration_ms=%d",
                request_id,
                tool_name,
                result_status,
                verified,
                mcp_is_error,
                round((time.monotonic() - invocation_started_at) * 1000),
            )
            return GatewayResult(status="allowed_and_executed", payload=res_dict)
        except TokenExpiredException:
            # Token expired client-side before send: remint once safely
            logger.warning(
                "ArmorIQ intent token expired before send request_id=%s action=%s retrying_once=true",
                request_id,
                tool_name,
            )
            try:
                plan_capture = self.client.capture_plan(
                    llm=model_name,
                    prompt=(intent_prompt or f"Execute tool {tool_name} with parameters")[:4000],
                    plan={
                        "goal": f"Invoke the permitted Keeper tool {tool_name}.",
                        "steps": [{"action": tool_name, "mcp": settings.ARMORIQ_MCP_NAME, "params": params}],
                    },
                )
                intent_token = self.client.get_intent_token(plan_capture=plan_capture, validity_seconds=60.0)
            except PolicyHoldException as e:
                return GatewayResult(status="held_by_armoriq", reason=str(e))
            except (PolicyBlockedException, InvalidTokenException, IntentMismatchException, DelegationException) as e:
                return GatewayResult(status="denied_by_armoriq", reason=str(e))
            except Exception as e:
                logger.error(
                    "ArmorIQ token remint failed before invocation request_id=%s action=%s "
                    "error_type=%s status_code=%s",
                    request_id,
                    tool_name,
                    type(e).__name__,
                    getattr(e, "status_code", None),
                )
                return GatewayResult(
                    status="unavailable_before_send",
                    reason=(
                        "ArmorIQ intent token remint failed before invocation "
                        f"({type(e).__name__}, HTTP {getattr(e, 'status_code', None)})."
                    ),
                )
            try:
                invocation_result = self.client.invoke(
                    mcp=settings.ARMORIQ_MCP_NAME,
                    action=tool_name,
                    intent_token=intent_token,
                    params=params,
                    user_email=user_email,
                )
            except TokenExpiredException as e:
                logger.error(
                    "ArmorIQ reminted token expired before send request_id=%s action=%s error_type=%s",
                    request_id,
                    tool_name,
                    type(e).__name__,
                )
                return GatewayResult(
                    status="unavailable_before_send",
                    reason="The reminted intent token expired before invocation; no tool was sent.",
                )
            except PolicyHoldException as e:
                logger.warning(
                    "ArmorIQ policy hold request_id=%s action=%s stage=invoke_after_remint",
                    request_id,
                    tool_name,
                )
                return GatewayResult(status="held_by_armoriq", reason=str(e))
            except (PolicyBlockedException, InvalidTokenException, IntentMismatchException, DelegationException) as e:
                logger.warning(
                    "ArmorIQ authorization denied request_id=%s action=%s "
                    "stage=invoke_after_remint error_type=%s",
                    request_id,
                    tool_name,
                    type(e).__name__,
                )
                return GatewayResult(status="denied_by_armoriq", reason=str(e))
            except MCPInvocationException as e:
                logger.error(
                    "ArmorIQ proxy invocation failed after remint request_id=%s action=%s "
                    "status_code=%s error_type=%s error_category=%s duration_ms=%d "
                    "outcome=ambiguous_after_send",
                    request_id,
                    tool_name,
                    e.status_code,
                    type(e).__name__,
                    _proxy_error_category(e),
                    round((time.monotonic() - invocation_started_at) * 1000),
                )
                return GatewayResult(
                    status="ambiguous_after_send",
                    reason=(
                        f"ArmorIQ proxy reported {_proxy_error_category(e)} "
                        f"(HTTP {e.status_code}); tool completion could not be confirmed."
                    ),
                    is_ambiguous=True,
                )
            except Exception as e:
                logger.error(
                    "ArmorIQ proxy invocation failed after remint request_id=%s action=%s "
                    "error_type=%s status_code=%s error_category=%s duration_ms=%d "
                    "outcome=ambiguous_after_send",
                    request_id,
                    tool_name,
                    type(e).__name__,
                    getattr(e, "status_code", None),
                    _proxy_error_category(e),
                    round((time.monotonic() - invocation_started_at) * 1000),
                )
                return GatewayResult(
                    status="ambiguous_after_send",
                    reason="ArmorIQ proxy invocation did not return a confirmed result.",
                    is_ambiguous=True,
                )
            result_status = getattr(invocation_result, "status", "success")
            if not isinstance(result_status, str):
                result_status = "success"
            verified = getattr(invocation_result, "verified", True)
            if not isinstance(verified, bool):
                verified = True
            res_dict = invocation_result.result if hasattr(invocation_result, "result") else invocation_result
            if result_status != "success" or not verified:
                logger.error(
                    "ArmorIQ proxy returned non-success after remint request_id=%s action=%s "
                    "sdk_status=%s verified=%s duration_ms=%d outcome=ambiguous_after_send",
                    request_id,
                    tool_name,
                    result_status,
                    verified,
                    round((time.monotonic() - invocation_started_at) * 1000),
                )
                return GatewayResult(
                    status="ambiguous_after_send",
                    reason=f"ArmorIQ invocation returned status={result_status}; execution could not be confirmed.",
                    is_ambiguous=True,
                )
            logger.info(
                "ArmorIQ proxy invocation completed after remint request_id=%s action=%s "
                "sdk_status=%s verified=%s mcp_is_error=%s duration_ms=%d",
                request_id,
                tool_name,
                result_status,
                verified,
                isinstance(res_dict, dict) and bool(res_dict.get("isError")),
                round((time.monotonic() - invocation_started_at) * 1000),
            )
            return GatewayResult(status="allowed_and_executed", payload=res_dict)
        except PolicyHoldException as e:
            logger.warning(
                "ArmorIQ policy hold request_id=%s action=%s stage=invoke",
                request_id,
                tool_name,
            )
            return GatewayResult(status="held_by_armoriq", reason=str(e))
        except (PolicyBlockedException, InvalidTokenException, IntentMismatchException, DelegationException) as e:
            logger.warning(
                "ArmorIQ authorization denied request_id=%s action=%s stage=invoke error_type=%s",
                request_id,
                tool_name,
                type(e).__name__,
            )
            return GatewayResult(status="denied_by_armoriq", reason=str(e))
        except MCPInvocationException as e:
            # Invocation exception after send -> classified as ambiguous
            logger.error(
                "ArmorIQ proxy invocation failed after send request_id=%s action=%s "
                "status_code=%s error_type=%s error_category=%s duration_ms=%d "
                "outcome=ambiguous_after_send",
                request_id,
                tool_name,
                e.status_code,
                type(e).__name__,
                _proxy_error_category(e),
                round((time.monotonic() - invocation_started_at) * 1000),
            )
            return GatewayResult(
                status="ambiguous_after_send",
                reason=(
                    f"ArmorIQ proxy reported {_proxy_error_category(e)} "
                    f"(HTTP {e.status_code}); tool completion could not be confirmed."
                ),
                is_ambiguous=True,
            )
        except Exception as e:
            # Network drop / timeout after send -> ambiguous
            logger.error(
                "ArmorIQ proxy invocation failed after send request_id=%s action=%s "
                "error_type=%s status_code=%s error_category=%s duration_ms=%d "
                "outcome=ambiguous_after_send",
                request_id,
                tool_name,
                type(e).__name__,
                getattr(e, "status_code", None),
                _proxy_error_category(e),
                round((time.monotonic() - invocation_started_at) * 1000),
            )
            return GatewayResult(
                status="ambiguous_after_send",
                reason="ArmorIQ proxy invocation did not return a confirmed result.",
                is_ambiguous=True,
            )

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
