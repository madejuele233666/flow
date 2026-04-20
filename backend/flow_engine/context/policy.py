"""Declarative capture/restore policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from flow_engine.state.machine import TaskState


class CaptureTrigger(str, Enum):
    """Lifecycle triggers that can stamp a snapshot."""

    PAUSE = "PAUSE"
    AUTO_PAUSE = "AUTO_PAUSE"
    BLOCK = "BLOCK"
    DONE = "DONE"
    START = "START"
    RESUME = "RESUME"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class PolicyDecision:
    capture: bool
    restore: bool


@dataclass(frozen=True)
class PolicyQuery:
    trigger: CaptureTrigger
    current_state: TaskState | None = None


class CaptureRestorePolicy:
    """Single source of truth for legal lifecycle context behavior."""

    def __init__(self, table: dict[PolicyQuery, PolicyDecision] | None = None) -> None:
        self._table = table or {
            PolicyQuery(CaptureTrigger.PAUSE): PolicyDecision(capture=True, restore=False),
            PolicyQuery(CaptureTrigger.AUTO_PAUSE): PolicyDecision(capture=True, restore=False),
            PolicyQuery(CaptureTrigger.BLOCK, TaskState.IN_PROGRESS): PolicyDecision(capture=True, restore=False),
            PolicyQuery(CaptureTrigger.BLOCK): PolicyDecision(capture=False, restore=False),
            PolicyQuery(CaptureTrigger.DONE): PolicyDecision(capture=True, restore=False),
            PolicyQuery(CaptureTrigger.START): PolicyDecision(capture=False, restore=True),
            PolicyQuery(CaptureTrigger.RESUME): PolicyDecision(capture=False, restore=True),
            PolicyQuery(CaptureTrigger.MANUAL): PolicyDecision(capture=True, restore=True),
        }

    def decision_for(
        self,
        trigger: CaptureTrigger,
        *,
        current_state: TaskState | None = None,
    ) -> PolicyDecision:
        query = PolicyQuery(trigger, current_state)
        if query in self._table:
            return self._table[query]
        return self._table[PolicyQuery(trigger)]

    def should_capture(
        self,
        trigger: CaptureTrigger,
        *,
        current_state: TaskState | None = None,
    ) -> bool:
        return self.decision_for(trigger, current_state=current_state).capture

    def should_restore(
        self,
        trigger: CaptureTrigger,
        *,
        current_state: TaskState | None = None,
    ) -> bool:
        return self.decision_for(trigger, current_state=current_state).restore
