"""Flow IPC V2 dataclass contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .constants import PROTOCOL_VERSION, TYPE_PUSH, TYPE_REQUEST, TYPE_RESPONSE


@dataclass(frozen=True)
class ClientInfo:
    name: str
    version: str


@dataclass(frozen=True)
class ServerInfo:
    name: str
    version: str


@dataclass(frozen=True)
class ErrorObject:
    code: str
    message: str
    retryable: bool
    data: dict[str, Any] | None = None


@dataclass(frozen=True)
class HelloParams:
    client: ClientInfo
    role: str
    transport: str
    protocol_min: int
    protocol_max: int
    capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HelloLimits:
    max_frame_bytes: int
    request_timeout_ms: int
    heartbeat_interval_ms: int
    heartbeat_miss_threshold: int


@dataclass(frozen=True)
class HelloResult:
    session_id: str
    protocol_version: int
    server: ServerInfo
    role: str
    transport: str
    limits: HelloLimits
    capabilities: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RequestFrame:
    id: str
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] | None = None
    v: int = PROTOCOL_VERSION
    type: str = TYPE_REQUEST


@dataclass(frozen=True)
class ResponseFrame:
    id: str
    result: Any = None
    error: ErrorObject | None = None
    meta: dict[str, Any] | None = None
    v: int = PROTOCOL_VERSION
    type: str = TYPE_RESPONSE


@dataclass(frozen=True)
class PushFrame:
    event: str
    data: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] | None = None
    v: int = PROTOCOL_VERSION
    type: str = TYPE_PUSH
