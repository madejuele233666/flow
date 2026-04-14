from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from flow_hud.ui_tokens.task_status import (
    TASK_STATUS_EMPTY_STATE,
    TASK_STATUS_EMPTY_TITLE,
    TASK_STATUS_OFFLINE_STATE,
    TASK_STATUS_OFFLINE_TITLE,
)


class TaskStatusMode(str, Enum):
    ACTIVE = "active"
    EMPTY = "empty"
    OFFLINE = "offline"


@dataclass(frozen=True)
class TaskStatusSnapshot:
    mode: TaskStatusMode
    title: str
    state_label: str
    duration_min: int | None
    break_suggested: bool
    task_id: int | None = None

    @classmethod
    def active(
        cls,
        *,
        task_id: int | None,
        title: str,
        state_label: str,
        duration_min: int | None,
        break_suggested: bool,
    ) -> TaskStatusSnapshot:
        return cls(
            mode=TaskStatusMode.ACTIVE,
            title=title,
            state_label=state_label,
            duration_min=duration_min,
            break_suggested=break_suggested,
            task_id=task_id,
        )

    @classmethod
    def empty(cls) -> TaskStatusSnapshot:
        return cls(
            mode=TaskStatusMode.EMPTY,
            title=TASK_STATUS_EMPTY_TITLE,
            state_label=TASK_STATUS_EMPTY_STATE,
            duration_min=None,
            break_suggested=False,
            task_id=None,
        )

    @classmethod
    def offline(cls) -> TaskStatusSnapshot:
        return cls(
            mode=TaskStatusMode.OFFLINE,
            title=TASK_STATUS_OFFLINE_TITLE,
            state_label=TASK_STATUS_OFFLINE_STATE,
            duration_min=None,
            break_suggested=False,
            task_id=None,
        )

    def with_duration(self, duration_min: int | None) -> TaskStatusSnapshot:
        return replace(self, duration_min=duration_min)


@dataclass(frozen=True)
class TaskStatusUpdatedPayload:
    snapshot: TaskStatusSnapshot
