import json
import logging
import re
import time
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.integrations.armoriq_gateway import ArmorIQGateway
from backend.app.services.mcp_tools import (
    GetBillInput,
    GetPaymentStatusInput,
    ListBillsInput,
    ProposePaymentInput,
    execute_tool,
    resolve_authorization_context,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])
logger = logging.getLogger(__name__)

_CORRELATION_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,100}\Z")


def _correlation_id(request: Request) -> str:
    value = request.headers.get("x-request-id", "")
    return value if _CORRELATION_ID_PATTERN.fullmatch(value) else "invalid"


def verify_mcp_auth(request: Request, authorization: Optional[str] = Header(None)):
    correlation_id = _correlation_id(request)
    if not ArmorIQGateway.verify_inbound_secret(authorization):
        logger.warning(
            "MCP request rejected correlation_id=%s reason=invalid_or_missing_bearer",
            correlation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "Invalid or missing MCP inbound bearer secret."},
        )
    logger.info("MCP request authenticated correlation_id=%s", correlation_id)


class MCPToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=64)
    arguments: Dict[str, Any] = Field(default_factory=dict)


TOOL_DEFINITIONS = [
    {
        "name": "list_bills",
        "description": "List bills for the configured household.",
        "inputSchema": ListBillsInput.model_json_schema(),
    },
    {
        "name": "get_bill",
        "description": "Get detailed bill information.",
        "inputSchema": GetBillInput.model_json_schema(),
    },
    {
        "name": "propose_payment",
        "description": "Propose payment for a bill. Keeper policy and ArmorIQ authorize execution.",
        "inputSchema": ProposePaymentInput.model_json_schema(),
    },
    {
        "name": "get_payment_status",
        "description": "Check the status of a payment attempt or bill.",
        "inputSchema": GetPaymentStatusInput.model_json_schema(),
    },
]


def _sse_message(payload: Dict[str, Any]) -> StreamingResponse:
    encoded = json.dumps(payload, separators=(",", ":"), default=str)
    return StreamingResponse(
        iter([f"event: message\ndata: {encoded}\n\n"]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _rpc_error(request_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": error}


@router.post("", dependencies=[Depends(verify_mcp_auth)])
def mcp_endpoint(
    request: Request,
    message: Dict[str, Any],
    db: Session = Depends(get_db),
):
    request_id = message.get("id")
    correlation_id = _correlation_id(request)
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        logger.warning(
            "MCP request rejected correlation_id=%s reason=invalid_jsonrpc",
            correlation_id,
        )
        return _sse_message(_rpc_error(request_id, -32600, "Invalid JSON-RPC request."))

    method = message["method"]
    trace_id = uuid.uuid4().hex
    logger.info(
        "MCP request received correlation_id=%s trace_id=%s method=%r",
        correlation_id,
        trace_id,
        method,
    )
    if method == "notifications/initialized":
        return Response(status_code=202)
    if method == "initialize":
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": settings.ARMORIQ_MCP_NAME, "version": "1.0.0"},
        }
        return _sse_message({"jsonrpc": "2.0", "id": request_id, "result": result})
    if method == "ping":
        return _sse_message({"jsonrpc": "2.0", "id": request_id, "result": {}})
    if method == "tools/list":
        return _sse_message({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOL_DEFINITIONS}})
    if method != "tools/call":
        return _sse_message(_rpc_error(request_id, -32601, "Method not found."))
    if request_id is None:
        return _sse_message(_rpc_error(None, -32600, "tools/call requires a request id."))

    try:
        tool_call = MCPToolCall.model_validate(message.get("params", {}))
        logger.info(
            "MCP tool call received correlation_id=%s trace_id=%s tool=%r",
            correlation_id,
            trace_id,
            tool_call.name,
        )
        context_token = tool_call.arguments.get("authorization_context")
        if not isinstance(context_token, str):
            raise HTTPException(status_code=401, detail="Signed MCP authorization context is required.")
        household_id = resolve_authorization_context(context_token)
        started_at = time.monotonic()
        logger.info(
            "MCP tool execution started correlation_id=%s trace_id=%s tool=%r",
            correlation_id,
            trace_id,
            tool_call.name,
        )
        result = execute_tool(db, household_id, tool_call.name, tool_call.arguments)
        logger.info(
            "MCP tool execution returned correlation_id=%s trace_id=%s tool=%r "
            "is_error=false duration_ms=%d",
            correlation_id,
            trace_id,
            tool_call.name,
            round((time.monotonic() - started_at) * 1000),
        )
        tool_result = {
            "content": [{"type": "text", "text": json.dumps(result, separators=(",", ":"), default=str)}],
            "isError": False,
        }
        return _sse_message({"jsonrpc": "2.0", "id": request_id, "result": tool_result})
    except ValidationError as exc:
        logger.warning(
            "MCP tool call rejected correlation_id=%s trace_id=%s reason=invalid_arguments",
            correlation_id,
            trace_id,
        )
        return _sse_message(_rpc_error(request_id, -32602, "Invalid tool arguments.", exc.errors()))
    except HTTPException as exc:
        logger.warning(
            "MCP tool call rejected correlation_id=%s trace_id=%s status=%s",
            correlation_id,
            trace_id,
            exc.status_code,
        )
        detail = exc.detail if isinstance(exc.detail, (dict, str)) else str(exc.detail)
        tool_result = {
            "content": [{"type": "text", "text": json.dumps({"error": detail}, default=str)}],
            "isError": True,
        }
        return _sse_message({"jsonrpc": "2.0", "id": request_id, "result": tool_result})
