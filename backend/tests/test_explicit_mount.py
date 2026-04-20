from __future__ import annotations

import asyncio
import multiprocessing
from pathlib import Path

from flow_engine.app import FlowApp
from flow_engine.client import LocalClient
from flow_engine.config import AppConfig, load_config
from flow_engine.context.mounts import MountKind, MountService


def test_mount_service_crud_and_ordering(tmp_path: Path) -> None:
    service = MountService(tmp_path / "mounts")

    file_item = service.add(1, MountKind.FILE, path="/tmp/doc.txt")
    url_item = service.add(1, MountKind.URL, url="https://example.com", note="docs")
    note_item = service.add(1, MountKind.NOTE, note="remember this")

    assert [item.kind for item in service.list(1)] == [MountKind.FILE, MountKind.URL, MountKind.NOTE]

    service.reorder(1, note_item.id, -1)
    ordered = service.list(1)
    assert ordered[0].id == note_item.id

    assert service.remove(1, url_item.id) is True
    assert service.remove(1, "missing") is False
    remaining = service.list(1)
    assert [item.id for item in remaining] == [note_item.id, file_item.id]


def _concurrent_mount_writer(mounts_dir: str, note: str) -> None:
    service = MountService(Path(mounts_dir))
    service.add(9, MountKind.NOTE, note=note)


def test_mount_service_concurrent_writes_preserve_all_mounts(tmp_path: Path) -> None:
    ctx_name = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
    ctx = multiprocessing.get_context(ctx_name)
    mounts_dir = str(tmp_path / "mounts")

    first = ctx.Process(target=_concurrent_mount_writer, args=(mounts_dir, "note-1"))
    second = ctx.Process(target=_concurrent_mount_writer, args=(mounts_dir, "note-2"))
    first.start()
    second.start()
    first.join()
    second.join()

    assert first.exitcode == 0
    assert second.exitcode == 0

    service = MountService(Path(mounts_dir))
    assert sorted(item.note for item in service.list(9)) == ["note-1", "note-2"]


def test_mounts_survive_task_lifecycle_and_default_config_creates_dirs(tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        config = AppConfig()
        config.paths.data_dir = tmp_path / "data"
        config.git.enabled = False
        config.git.auto_commit = False
        config.notifications.enabled = False
        config.plugin_breaker.safe_mode = True
        config.context.enabled = False

        app = FlowApp(config)
        client = LocalClient(app)
        try:
            await client.add_task(title="alpha")
            await client.start_task(1)
            mounted = await client.add_mount("/tmp/doc.txt")

            await client.pause_task()
            assert len(await client.list_mounts(task_id=1)) == 1

            await client.resume_task(1)
            assert len(await client.list_mounts(task_id=1)) == 1

            await client.done_task()
            listed = await client.list_mounts(task_id=1)
            assert listed[0]["id"] == mounted["id"]
        finally:
            await app.shutdown()

    monkeypatch.setenv("FLOW_DATA_DIR", str(tmp_path / "configured"))
    config = load_config()
    try:
        assert config.context.capture_on_switch is True
        assert config.context.mount_enabled is True
        assert config.context.trail_enabled is True
        assert config.paths.mounts_path.exists()
        assert config.paths.trails_path.exists()
    finally:
        monkeypatch.delenv("FLOW_DATA_DIR", raising=False)

    asyncio.run(scenario())
