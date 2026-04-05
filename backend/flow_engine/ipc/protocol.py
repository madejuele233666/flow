"""Backend IPC protocol wrapper around shared flow_ipc contract."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

try:
    from flow_ipc import (
        ERR_DAEMON_SHUTTING_DOWN,
        ERR_INTERNAL,
        ERR_INVALID_FRAME,
        ERR_INVALID_PARAMS,
        ERR_METHOD_NOT_FOUND,
        ERR_REQUEST_TIMEOUT,
        ERR_ROLE_MISMATCH,
        ERR_UNSUPPORTED_PROTOCOL,
        EVENT_SESSION_CLOSING,
        EVENT_SESSION_KEEPALIVE,
        METHOD_SESSION_BYE,
        METHOD_SESSION_HELLO,
        METHOD_SESSION_PING,
        PROTOCOL_VERSION,
        ROLE_PUSH,
        ROLE_RPC,
        TRANSPORT_TCP,
        TRANSPORT_UNIX,
        ErrorObject,
        Frame,
        HelloLimits,
        HelloParams,
        HelloResult,
        PushFrame,
        RequestFrame,
        ResponseFrame,
        decode_frame,
        encode_frame,
        frame_from_dict,
        make_hello_params,
        make_hello_result,
        parse_hello_params,
        parse_hello_result,
    )
except ModuleNotFoundError:
    shared_dir = Path(__file__).resolve().parents[3] / "shared"
    if str(shared_dir) not in sys.path:
        sys.path.insert(0, str(shared_dir))
    from flow_ipc import (  # type: ignore[no-redef]
        ERR_DAEMON_SHUTTING_DOWN,
        ERR_INTERNAL,
        ERR_INVALID_FRAME,
        ERR_INVALID_PARAMS,
        ERR_METHOD_NOT_FOUND,
        ERR_REQUEST_TIMEOUT,
        ERR_ROLE_MISMATCH,
        ERR_UNSUPPORTED_PROTOCOL,
        EVENT_SESSION_CLOSING,
        EVENT_SESSION_KEEPALIVE,
        METHOD_SESSION_BYE,
        METHOD_SESSION_HELLO,
        METHOD_SESSION_PING,
        PROTOCOL_VERSION,
        ROLE_PUSH,
        ROLE_RPC,
        TRANSPORT_TCP,
        TRANSPORT_UNIX,
        ErrorObject,
        Frame,
        HelloLimits,
        HelloParams,
        HelloResult,
        PushFrame,
        RequestFrame,
        ResponseFrame,
        decode_frame,
        encode_frame,
        frame_from_dict,
        make_hello_params,
        make_hello_result,
        parse_hello_params,
        parse_hello_result,
    )

Request = RequestFrame
Response = ResponseFrame
Push = PushFrame
Error = ErrorObject


def make_request(method: str, params: dict | None = None, req_id: str | None = None) -> Request:
    """Create request frame with generated id."""
    return Request(id=req_id or uuid4().hex[:8], method=method, params=params or {})


def make_error(
    code: str = ERR_INTERNAL,
    message: str = "internal error",
    *,
    retryable: bool = False,
    data: dict | None = None,
) -> Error:
    """Create structured error object."""
    return Error(code=code, message=message, retryable=retryable, data=data)


def make_response(req_id: str, *, result: object = None, error: Error | None = None) -> Response:
    """Create response frame."""
    return Response(id=req_id, result=result, error=error)


def encode(frame: Frame) -> bytes:
    """Encode frame to NDJSON bytes."""
    return encode_frame(frame)


def decode(data: bytes) -> Frame:
    """Decode NDJSON bytes to typed frame."""
    return decode_frame(data)
