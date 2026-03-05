"""Daemon 模块入口 — 支持 python -m flow_engine.daemon 启动."""

import asyncio
from flow_engine.daemon import run_daemon

if __name__ == "__main__":
    asyncio.run(run_daemon())
