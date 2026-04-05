"""Flow IPC V2 NDJSON codec and frame parsing."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .constants import ERR_INVALID_FRAME, PROTOCOL_VERSION, TYPE_PUSH, TYPE_REQUEST, TYPE_RESPONSE
from .models import (
    ClientInfo,
    ErrorObject,
    HelloLimits,
    HelloParams,
    HelloResult,
    PushFrame,
    RequestFrame,
    ResponseFrame,
    ServerInfo,
)


class ProtocolDecodeError(ValueError):
    """Decode error with stable IPC error code."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = ERR_INVALID_FRAME


Frame = RequestFrame | ResponseFrame | PushFrame


def _is_strict_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def encode_frame(frame: Frame) -> bytes:
    """Encode frame to UTF-8 NDJSON."""
    raw = asdict(frame)
    frame_from_dict(raw)
    return (json.dumps(raw, ensure_ascii=False) + "\n").encode("utf-8")


def decode_frame(data: bytes) -> Frame:
    """Decode UTF-8 NDJSON to typed frame."""
    try:
        raw = json.loads(data.decode("utf-8").strip())
    except json.JSONDecodeError as exc:
        raise ProtocolDecodeError(f"invalid json frame: {exc}") from exc
    return frame_from_dict(raw)


def make_hello_params(
    *,
    client_name: str,
    client_version: str,
    role: str,
    transport: str,
    protocol_min: int,
    protocol_max: int,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Build canonical hello request params payload."""
    hello = HelloParams(
        client=ClientInfo(name=client_name, version=client_version),
        role=role,
        transport=transport,
        protocol_min=protocol_min,
        protocol_max=protocol_max,
        capabilities=list(capabilities or []),
    )
    return hello_params_to_dict(hello)


def hello_params_to_dict(hello: HelloParams) -> dict[str, Any]:
    """Serialize hello params dataclass to wire payload."""
    return {
        "client": {"name": hello.client.name, "version": hello.client.version},
        "role": hello.role,
        "transport": hello.transport,
        "protocol_min": hello.protocol_min,
        "protocol_max": hello.protocol_max,
        "capabilities": list(hello.capabilities),
    }


def parse_hello_params(raw: Any) -> HelloParams:
    """Parse and validate hello request params payload."""
    if not isinstance(raw, dict):
        raise ProtocolDecodeError("hello.params must be object")
    client_raw = raw.get("client")
    if not isinstance(client_raw, dict):
        raise ProtocolDecodeError("hello.params.client must be object")
    client_name = client_raw.get("name")
    client_version = client_raw.get("version")
    if not isinstance(client_name, str) or not client_name:
        raise ProtocolDecodeError("hello.params.client.name is required")
    if not isinstance(client_version, str) or not client_version:
        raise ProtocolDecodeError("hello.params.client.version is required")

    role = raw.get("role")
    transport = raw.get("transport")
    protocol_min = raw.get("protocol_min")
    protocol_max = raw.get("protocol_max")
    capabilities = raw.get("capabilities", [])

    if not isinstance(role, str) or not role:
        raise ProtocolDecodeError("hello.params.role is required")
    if not isinstance(transport, str) or not transport:
        raise ProtocolDecodeError("hello.params.transport is required")
    if not _is_strict_int(protocol_min) or not _is_strict_int(protocol_max):
        raise ProtocolDecodeError("hello.params.protocol_min/protocol_max must be integers")
    if not isinstance(capabilities, list) or any(not isinstance(x, str) for x in capabilities):
        raise ProtocolDecodeError("hello.params.capabilities must be list[str]")

    return HelloParams(
        client=ClientInfo(name=client_name, version=client_version),
        role=role,
        transport=transport,
        protocol_min=protocol_min,
        protocol_max=protocol_max,
        capabilities=list(capabilities),
    )


def make_hello_result(
    *,
    session_id: str,
    protocol_version: int,
    server_name: str,
    server_version: str,
    role: str,
    transport: str,
    max_frame_bytes: int,
    request_timeout_ms: int,
    heartbeat_interval_ms: int,
    heartbeat_miss_threshold: int,
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    """Build canonical hello response result payload."""
    hello = HelloResult(
        session_id=session_id,
        protocol_version=protocol_version,
        server=ServerInfo(name=server_name, version=server_version),
        role=role,
        transport=transport,
        limits=HelloLimits(
            max_frame_bytes=max_frame_bytes,
            request_timeout_ms=request_timeout_ms,
            heartbeat_interval_ms=heartbeat_interval_ms,
            heartbeat_miss_threshold=heartbeat_miss_threshold,
        ),
        capabilities=list(capabilities or []),
    )
    return hello_result_to_dict(hello)


def hello_result_to_dict(hello: HelloResult) -> dict[str, Any]:
    """Serialize hello result dataclass to wire payload."""
    return {
        "session_id": hello.session_id,
        "protocol_version": hello.protocol_version,
        "server": {"name": hello.server.name, "version": hello.server.version},
        "role": hello.role,
        "transport": hello.transport,
        "capabilities": list(hello.capabilities),
        "limits": {
            "max_frame_bytes": hello.limits.max_frame_bytes,
            "request_timeout_ms": hello.limits.request_timeout_ms,
            "heartbeat_interval_ms": hello.limits.heartbeat_interval_ms,
            "heartbeat_miss_threshold": hello.limits.heartbeat_miss_threshold,
        },
    }


def parse_hello_result(raw: Any) -> HelloResult:
    """Parse and validate hello response result payload."""
    if not isinstance(raw, dict):
        raise ProtocolDecodeError("hello.result must be object")
    session_id = raw.get("session_id")
    protocol_version = raw.get("protocol_version")
    server_raw = raw.get("server")
    role = raw.get("role")
    transport = raw.get("transport")
    if "capabilities" not in raw:
        raise ProtocolDecodeError("hello.result.capabilities is required")
    capabilities = raw["capabilities"]
    limits_raw = raw.get("limits")

    if not isinstance(session_id, str) or not session_id:
        raise ProtocolDecodeError("hello.result.session_id is required")
    if not _is_strict_int(protocol_version):
        raise ProtocolDecodeError("hello.result.protocol_version must be integer")
    if not isinstance(server_raw, dict):
        raise ProtocolDecodeError("hello.result.server must be object")
    server_name = server_raw.get("name")
    server_version = server_raw.get("version")
    if not isinstance(server_name, str) or not server_name:
        raise ProtocolDecodeError("hello.result.server.name is required")
    if not isinstance(server_version, str) or not server_version:
        raise ProtocolDecodeError("hello.result.server.version is required")
    if not isinstance(role, str) or not role:
        raise ProtocolDecodeError("hello.result.role is required")
    if not isinstance(transport, str) or not transport:
        raise ProtocolDecodeError("hello.result.transport is required")
    if not isinstance(capabilities, list) or any(not isinstance(x, str) for x in capabilities):
        raise ProtocolDecodeError("hello.result.capabilities must be list[str]")
    if not isinstance(limits_raw, dict):
        raise ProtocolDecodeError("hello.result.limits must be object")

    max_frame_bytes = limits_raw.get("max_frame_bytes")
    request_timeout_ms = limits_raw.get("request_timeout_ms")
    heartbeat_interval_ms = limits_raw.get("heartbeat_interval_ms")
    heartbeat_miss_threshold = limits_raw.get("heartbeat_miss_threshold")
    if not _is_strict_int(max_frame_bytes) or max_frame_bytes <= 0:
        raise ProtocolDecodeError("hello.result.limits.max_frame_bytes must be positive integer")
    if not _is_strict_int(request_timeout_ms) or request_timeout_ms <= 0:
        raise ProtocolDecodeError("hello.result.limits.request_timeout_ms must be positive integer")
    if not _is_strict_int(heartbeat_interval_ms) or heartbeat_interval_ms <= 0:
        raise ProtocolDecodeError("hello.result.limits.heartbeat_interval_ms must be positive integer")
    if not _is_strict_int(heartbeat_miss_threshold) or heartbeat_miss_threshold <= 0:
        raise ProtocolDecodeError("hello.result.limits.heartbeat_miss_threshold must be positive integer")

    return HelloResult(
        session_id=session_id,
        protocol_version=protocol_version,
        server=ServerInfo(name=server_name, version=server_version),
        role=role,
        transport=transport,
        limits=HelloLimits(
            max_frame_bytes=max_frame_bytes,
            request_timeout_ms=request_timeout_ms,
            heartbeat_interval_ms=heartbeat_interval_ms,
            heartbeat_miss_threshold=heartbeat_miss_threshold,
        ),
        capabilities=list(capabilities),
    )


def frame_from_dict(raw: dict[str, Any]) -> Frame:
    """Create typed frame from dict with V2 validation."""
    if raw.get("v") != PROTOCOL_VERSION:
        raise ProtocolDecodeError(f"unsupported protocol version: {raw.get('v')}")

    frame_type = raw.get("type")
    if frame_type == TYPE_REQUEST:
        return _request_from_dict(raw)
    if frame_type == TYPE_RESPONSE:
        return _response_from_dict(raw)
    if frame_type == TYPE_PUSH:
        return _push_from_dict(raw)
    raise ProtocolDecodeError(f"unknown frame type: {frame_type}")


def _request_from_dict(raw: dict[str, Any]) -> RequestFrame:
    frame_id = raw.get("id")
    method = raw.get("method")
    params = raw.get("params", {})
    if not isinstance(frame_id, str) or not frame_id:
        raise ProtocolDecodeError("request.id is required")
    if not isinstance(method, str) or not method:
        raise ProtocolDecodeError("request.method is required")
    if not isinstance(params, dict):
        raise ProtocolDecodeError("request.params must be object")
    meta = raw.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise ProtocolDecodeError("request.meta must be object")
    return RequestFrame(id=frame_id, method=method, params=params, meta=meta)


def _response_from_dict(raw: dict[str, Any]) -> ResponseFrame:
    frame_id = raw.get("id")
    if not isinstance(frame_id, str) or not frame_id:
        raise ProtocolDecodeError("response.id is required")
    has_result = "result" in raw and raw.get("result") is not None
    has_error = raw.get("error") is not None
    if has_result == has_error:
        raise ProtocolDecodeError("response must contain exactly one of result or error")
    error_obj: ErrorObject | None = None
    if has_error:
        error_raw = raw["error"]
        if not isinstance(error_raw, dict):
            raise ProtocolDecodeError("response.error must be object")
        code = error_raw.get("code")
        message = error_raw.get("message")
        retryable = error_raw.get("retryable")
        data = error_raw.get("data")
        if not isinstance(code, str) or not code:
            raise ProtocolDecodeError("error.code is required")
        if not isinstance(message, str):
            raise ProtocolDecodeError("error.message is required")
        if not isinstance(retryable, bool):
            raise ProtocolDecodeError("error.retryable is required")
        if data is not None and not isinstance(data, dict):
            raise ProtocolDecodeError("error.data must be object")
        error_obj = ErrorObject(code=code, message=message, retryable=retryable, data=data)
    meta = raw.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise ProtocolDecodeError("response.meta must be object")
    return ResponseFrame(
        id=frame_id,
        result=raw.get("result"),
        error=error_obj,
        meta=meta,
    )


def _push_from_dict(raw: dict[str, Any]) -> PushFrame:
    event = raw.get("event")
    data = raw.get("data", {})
    if not isinstance(event, str) or not event:
        raise ProtocolDecodeError("push.event is required")
    if not isinstance(data, dict):
        raise ProtocolDecodeError("push.data must be object")
    meta = raw.get("meta")
    if meta is not None and not isinstance(meta, dict):
        raise ProtocolDecodeError("push.meta must be object")
    return PushFrame(event=event, data=data, meta=meta)
