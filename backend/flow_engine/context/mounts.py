"""Explicit task-bound mounts."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)

try:
    from filelock import FileLock

    _HAS_FILELOCK = True
except ImportError:  # pragma: no cover - optional dependency path
    _HAS_FILELOCK = False
    FileLock = None  # type: ignore[assignment]

try:  # pragma: no cover - platform-specific import
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - non-Unix path
    _HAS_FCNTL = False


class _PathLock:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle = None

    def __enter__(self) -> _PathLock:
        if not _HAS_FCNTL:
            raise RuntimeError("MountService requires filelock or fcntl-based locking")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("a+", encoding="utf-8")
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *args: object) -> None:
        if self._handle is None:
            return
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None


class MountKind(str, Enum):
    FILE = "file"
    URL = "url"
    NOTE = "note"


@dataclass
class MountedItem:
    id: str
    task_id: int
    kind: MountKind
    path: str = ""
    url: str = ""
    note: str = ""
    pinned: bool = False
    order: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> MountedItem:
        return cls(
            id=str(raw["id"]),
            task_id=int(raw["task_id"]),
            kind=MountKind(str(raw["kind"])),
            path=str(raw.get("path", "")),
            url=str(raw.get("url", "")),
            note=str(raw.get("note", "")),
            pinned=bool(raw.get("pinned", False)),
            order=int(raw.get("order", 0)),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
        )


class MountService:
    """Persist explicit mounts independently from snapshots."""

    def __init__(self, mounts_dir: Path, *, lock_timeout: float = 10.0) -> None:
        self._dir = mounts_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock_timeout = lock_timeout

    def add(
        self,
        task_id: int,
        kind: MountKind,
        *,
        path: str = "",
        url: str = "",
        note: str = "",
        pinned: bool = False,
    ) -> MountedItem:
        def _mutate(items: list[MountedItem]) -> MountedItem:
            next_order = max((item.order for item in items), default=-1) + 1
            mounted = MountedItem(
                id=uuid4().hex,
                task_id=task_id,
                kind=kind,
                path=path,
                url=url,
                note=note,
                pinned=pinned,
                order=next_order,
            )
            items.append(mounted)
            return mounted

        return self._update(task_id, _mutate)

    def remove(self, task_id: int, mount_id: str) -> bool:
        removed = False

        def _mutate(items: list[MountedItem]) -> bool:
            nonlocal removed
            new_items = [item for item in items if item.id != mount_id]
            removed = len(new_items) != len(items)
            items[:] = new_items
            return removed

        return self._update(task_id, _mutate)

    def list(self, task_id: int) -> list[MountedItem]:
        return sorted(self._load(task_id), key=lambda item: (item.order, item.created_at))

    def reorder(self, task_id: int, mount_id: str, new_order: int) -> None:
        def _mutate(items: list[MountedItem]) -> None:
            for item in items:
                if item.id == mount_id:
                    item.order = new_order
                    break

        self._update(task_id, _mutate)

    def _path_for(self, task_id: int) -> Path:
        return self._dir / f"{task_id}.json"

    def _lock_for(self, path: Path):
        if _HAS_FILELOCK:
            return FileLock(str(path) + ".lock", timeout=self._lock_timeout)
        return _PathLock(path.with_suffix(path.suffix + ".lock"))

    def _load(self, task_id: int) -> list[MountedItem]:
        path = self._path_for(task_id)
        if not path.exists():
            return []
        lock = self._lock_for(path)
        with lock:
            data = json.loads(path.read_text(encoding="utf-8"))
        return [MountedItem.from_dict(item) for item in data]

    def _update(self, task_id: int, mutate):
        path = self._path_for(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = self._lock_for(path)
        with lock:
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                items = [MountedItem.from_dict(item) for item in raw]
            else:
                items = []
            result = mutate(items)
            path.write_text(
                json.dumps([item.to_dict() for item in items], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug("mounts saved: task=%s path=%s", task_id, path)
            return result
