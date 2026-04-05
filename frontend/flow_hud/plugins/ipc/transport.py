from __future__ import annotations

import asyncio
from dataclasses import dataclass

from flow_hud.plugins.ipc.protocol import TRANSPORT_TCP, TRANSPORT_UNIX


@dataclass(frozen=True)
class IpcEndpoint:
    transport: str
    host: str
    port: int
    socket_path: str


class SocketTransportAdapter:
    """Transport adapter for unix/tcp IPC connections."""

    async def open_connection(self, endpoint: IpcEndpoint) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if endpoint.transport == TRANSPORT_UNIX:
            return await asyncio.open_unix_connection(endpoint.socket_path)
        if endpoint.transport == TRANSPORT_TCP:
            return await asyncio.open_connection(endpoint.host, endpoint.port)
        raise ValueError(f"unsupported transport: {endpoint.transport}")

