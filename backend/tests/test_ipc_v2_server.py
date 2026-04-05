from __future__ import annotations

import asyncio
from pathlib import Path

from flow_engine.ipc.protocol import (
    ERR_DAEMON_SHUTTING_DOWN,
    ERR_INVALID_FRAME,
    ERR_ROLE_MISMATCH,
    ERR_UNSUPPORTED_PROTOCOL,
    EVENT_SESSION_CLOSING,
    EVENT_SESSION_KEEPALIVE,
    METHOD_SESSION_BYE,
    METHOD_SESSION_HELLO,
    METHOD_SESSION_PING,
    PROTOCOL_VERSION,
    Push,
    ROLE_PUSH,
    ROLE_RPC,
    Response,
    TRANSPORT_TCP,
    TRANSPORT_UNIX,
    decode,
    encode,
    make_request,
)
from flow_engine.ipc.server import IPCServer


def _hello_params(role: str = ROLE_RPC, transport: str = TRANSPORT_TCP) -> dict:
    return {
        "client": {"name": "pytest-client", "version": "0.1.0"},
        "role": role,
        "transport": transport,
        "protocol_min": 2,
        "protocol_max": 2,
        "capabilities": [],
    }


async def _start_server(socket_path: Path) -> IPCServer:
    server = IPCServer(socket_path=socket_path, tcp_host="127.0.0.1", tcp_port=0)

    async def _echo(params: dict) -> dict:
        await asyncio.sleep(0)
        return {"echo": params}

    server.register("echo", _echo)
    await server.start()
    return server


def test_handshake_required_non_hello_rejected(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            writer.write(encode(make_request("echo", {"x": 1})))
            await writer.drain()

            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is not None
            assert resp.error.code == ERR_INVALID_FRAME
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_hello_success_returns_limits(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_RPC))))
            await writer.drain()

            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is None
            assert isinstance(resp.result, dict)
            assert resp.result["protocol_version"] == PROTOCOL_VERSION
            limits = resp.result["limits"]
            assert limits["max_frame_bytes"] == 65536
            assert limits["request_timeout_ms"] == 30000
            assert limits["heartbeat_interval_ms"] == 15000
            assert limits["heartbeat_miss_threshold"] == 2
            writer.close()
            await writer.wait_closed()
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_unsupported_protocol_rejected(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            params = _hello_params(ROLE_RPC)
            params["protocol_min"] = 3
            params["protocol_max"] = 3
            writer.write(encode(make_request(METHOD_SESSION_HELLO, params)))
            await writer.drain()

            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is not None
            assert resp.error.code == ERR_UNSUPPORTED_PROTOCOL
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_parseable_hello_schema_violation_returns_invalid_frame(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            params = _hello_params(ROLE_RPC)
            params.pop("role")
            writer.write(encode(make_request(METHOD_SESSION_HELLO, params)))
            await writer.drain()

            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is not None
            assert resp.error.code == ERR_INVALID_FRAME
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_push_role_rejects_business_request(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        writer = None
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_PUSH))))
            await writer.drain()
            _ = await reader.readline()

            writer.write(encode(make_request("echo", {"x": 1})))
            await writer.drain()
            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is not None
            assert resp.error.code == ERR_ROLE_MISMATCH
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()
            await server.stop()

    asyncio.run(scenario())


def test_response_result_error_xor_rule() -> None:
    raw = (
        '{"v":2,"type":"response","id":"r1","result":{"ok":true},'
        '"error":{"code":"ERR_INTERNAL","message":"x","retryable":false}}\n'
    ).encode("utf-8")
    try:
        decode(raw)
        assert False, "decode_frame must reject response with both result and error"
    except Exception as exc:  # noqa: BLE001
        assert "exactly one of result or error" in str(exc)


def test_ping_and_bye_control_methods(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_RPC))))
            await writer.drain()
            _ = await reader.readline()

            writer.write(encode(make_request(METHOD_SESSION_PING, {})))
            await writer.drain()
            ping_line = await reader.readline()
            ping_resp = decode(ping_line)
            assert isinstance(ping_resp, Response)
            assert ping_resp.error is None
            assert ping_resp.result == {"pong": True}

            writer.write(encode(make_request(METHOD_SESSION_BYE, {})))
            await writer.drain()
            bye_line = await reader.readline()
            bye_resp = decode(bye_line)
            assert isinstance(bye_resp, Response)
            assert bye_resp.error is None
            assert bye_resp.result == {"bye": True}
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_shutdown_emits_session_closing_push(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        reader = None
        writer = None
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_PUSH))))
            await writer.drain()
            _ = await reader.readline()

            stop_task = asyncio.create_task(server.stop())
            line = await asyncio.wait_for(reader.readline(), timeout=1.0)
            frame = decode(line)
            assert isinstance(frame, Push)
            assert frame.event == EVENT_SESSION_CLOSING
            await stop_task
        finally:
            if writer:
                writer.close()
                await writer.wait_closed()

    asyncio.run(scenario())


def test_hello_success_over_unix_transport(tmp_path: Path) -> None:
    async def scenario() -> None:
        socket_path = tmp_path / "daemon.sock"
        server = await _start_server(socket_path)
        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_RPC, TRANSPORT_UNIX))))
            await writer.drain()
            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is None
            assert isinstance(resp.result, dict)
            assert resp.result["transport"] == TRANSPORT_UNIX
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_hello_push_success_over_unix_transport(tmp_path: Path) -> None:
    async def scenario() -> None:
        socket_path = tmp_path / "daemon.sock"
        server = await _start_server(socket_path)
        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_PUSH, TRANSPORT_UNIX))))
            await writer.drain()
            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is None
            assert isinstance(resp.result, dict)
            assert resp.result["role"] == ROLE_PUSH
            assert resp.result["transport"] == TRANSPORT_UNIX
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_unsupported_protocol_rejected_over_unix_transport(tmp_path: Path) -> None:
    async def scenario() -> None:
        socket_path = tmp_path / "daemon.sock"
        server = await _start_server(socket_path)
        try:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            params = _hello_params(ROLE_RPC, TRANSPORT_UNIX)
            params["protocol_min"] = 3
            params["protocol_max"] = 3
            writer.write(encode(make_request(METHOD_SESSION_HELLO, params)))
            await writer.drain()
            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is not None
            assert resp.error.code == ERR_UNSUPPORTED_PROTOCOL
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_shutdown_rejects_business_method_with_structured_code(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_RPC))))
            await writer.drain()
            _ = await reader.readline()

            server._shutting_down = True  # simulate draining phase while connection is still alive
            writer.write(encode(make_request("echo", {"x": 1})))
            await writer.drain()
            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is not None
            assert resp.error.code == ERR_DAEMON_SHUTTING_DOWN
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_client_sent_push_frame_rejected(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = await _start_server(tmp_path / "daemon.sock")
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_RPC))))
            await writer.drain()
            _ = await reader.readline()

            writer.write(b'{"v":2,"type":"push","id":"p1","event":"fake.client.push","data":{}}\n')
            await writer.drain()
            line = await reader.readline()
            resp = decode(line)
            assert isinstance(resp, Response)
            assert resp.error is not None
            assert resp.error.code == ERR_INVALID_FRAME
            assert "must be request" in resp.error.message
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_keepalive_push_emitted_with_negotiated_interval(tmp_path: Path) -> None:
    async def scenario() -> None:
        server = IPCServer(
            socket_path=tmp_path / "daemon.sock",
            tcp_host="127.0.0.1",
            tcp_port=0,
            heartbeat_interval_ms=50,
            heartbeat_miss_threshold=2,
        )
        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.bound_tcp_port)
            writer.write(encode(make_request(METHOD_SESSION_HELLO, _hello_params(ROLE_PUSH))))
            await writer.drain()
            _ = await reader.readline()

            line = await asyncio.wait_for(reader.readline(), timeout=0.3)
            frame = decode(line)
            assert isinstance(frame, Push)
            assert frame.event == EVENT_SESSION_KEEPALIVE
        finally:
            await server.stop()

    asyncio.run(scenario())
