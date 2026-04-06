from __future__ import annotations

import asyncio
from pathlib import Path

from flow_engine.ipc.client import IPCClient
from flow_engine.ipc.protocol import (
    METHOD_SESSION_HELLO,
    PROTOCOL_VERSION,
    ROLE_RPC,
    TRANSPORT_UNIX,
    decode,
    encode,
    make_hello_result,
    make_request,
    make_response,
)


async def _start_bad_hello_server(socket_path: Path, *, protocol_version: int) -> asyncio.AbstractServer:
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            req = decode(line)
            if getattr(req, "method", None) != METHOD_SESSION_HELLO:
                return
            result = make_hello_result(
                session_id="sess_bad",
                protocol_version=protocol_version,
                server_name="flow-engine",
                server_version="0.1.0",
                role=ROLE_RPC,
                transport=TRANSPORT_UNIX,
                max_frame_bytes=65536,
                request_timeout_ms=10000,
                heartbeat_interval_ms=3000,
                heartbeat_miss_threshold=2,
                capabilities=[],
            )
            writer.write(encode(make_response(req.id, result=result)))
            await writer.drain()
        finally:
            writer.close()

    return await asyncio.start_unix_server(handler, path=str(socket_path))


def test_client_connect_rejects_hello_protocol_version_mismatch(tmp_path: Path) -> None:
    async def scenario() -> None:
        socket_path = tmp_path / "daemon.sock"
        server = await _start_bad_hello_server(socket_path, protocol_version=PROTOCOL_VERSION + 1)
        try:
            client = IPCClient(socket_path=socket_path)
            try:
                await client.connect()
                assert False, "connect() must fail when hello protocol_version mismatches"
            except ConnectionError as exc:
                assert "protocol_version mismatch" in str(exc)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())
