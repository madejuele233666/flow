from __future__ import annotations

import pytest

from flow_engine.ipc.protocol import Error, Response, encode, make_error, parse_hello_params, parse_hello_result


def test_encode_rejects_response_without_result_or_error() -> None:
    with pytest.raises(Exception, match="exactly one of result or error"):
        encode(Response(id="r1"))


def test_encode_rejects_response_with_both_result_and_error() -> None:
    err: Error = make_error("ERR_INTERNAL", "x", retryable=False)
    with pytest.raises(Exception, match="exactly one of result or error"):
        encode(Response(id="r2", result={"ok": True}, error=err))


def test_encode_accepts_response_with_only_result() -> None:
    payload = encode(Response(id="r3", result={"ok": True}))
    assert payload.endswith(b"\n")


def test_parse_hello_params_rejects_bool_protocol_bounds() -> None:
    with pytest.raises(Exception, match="protocol_min/protocol_max must be integers"):
        parse_hello_params(
            {
                "client": {"name": "hud", "version": "0.1.0"},
                "role": "rpc",
                "transport": "unix",
                "protocol_min": True,
                "protocol_max": 2,
                "capabilities": [],
            }
        )


def test_parse_hello_result_rejects_bool_numeric_fields() -> None:
    with pytest.raises(Exception, match="protocol_version must be integer"):
        parse_hello_result(
            {
                "session_id": "sess_x",
                "protocol_version": True,
                "server": {"name": "flow-engine", "version": "0.1.0"},
                "role": "rpc",
                "transport": "unix",
                "capabilities": [],
                "limits": {
                    "max_frame_bytes": 65536,
                    "request_timeout_ms": 10000,
                    "heartbeat_interval_ms": 3000,
                    "heartbeat_miss_threshold": 2,
                },
            }
        )


def test_parse_hello_result_requires_capabilities_field() -> None:
    with pytest.raises(Exception, match="capabilities is required"):
        parse_hello_result(
            {
                "session_id": "sess_x",
                "protocol_version": 2,
                "server": {"name": "flow-engine", "version": "0.1.0"},
                "role": "rpc",
                "transport": "unix",
                "limits": {
                    "max_frame_bytes": 65536,
                    "request_timeout_ms": 10000,
                    "heartbeat_interval_ms": 3000,
                    "heartbeat_miss_threshold": 2,
                },
            }
        )

    with pytest.raises(Exception, match="max_frame_bytes must be positive integer"):
        parse_hello_result(
            {
                "session_id": "sess_x",
                "protocol_version": 2,
                "server": {"name": "flow-engine", "version": "0.1.0"},
                "role": "rpc",
                "transport": "unix",
                "capabilities": [],
                "limits": {
                    "max_frame_bytes": False,
                    "request_timeout_ms": 10000,
                    "heartbeat_interval_ms": 3000,
                    "heartbeat_miss_threshold": 2,
                },
            }
        )
