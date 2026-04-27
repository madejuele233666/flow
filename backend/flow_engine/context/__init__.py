"""上下文捕获包 — 桌面现场插件系统."""

from flow_engine.context.models import ContextKind, FIELD_CLASSIFICATION
from flow_engine.context.browser_session import (
    ActivityWatchBrowserSessionProvider,
    BrowserSessionContextPlugin,
    BrowserSessionProvider,
    BrowserSessionSignal,
)
from flow_engine.context.mounts import MountKind, MountService, MountedItem
from flow_engine.context.policy import CaptureRestorePolicy, CaptureTrigger
from flow_engine.context.recovery import RESTORE_PRIORITY, RecoveryPriority, RestoreResult
from flow_engine.context.recovery_execution import (
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
    RecoveryExecutionService,
    RecoveryExecutorRegistry,
    RecoveryPlanner,
    RecoveryReport,
    WindowsDefaultOpenExecutor,
)
from flow_engine.context.trail import TrailCollector, TrailEvent, TrailStore

__all__ = [
    "CaptureRestorePolicy",
    "CaptureTrigger",
    "ActivityWatchBrowserSessionProvider",
    "BrowserSessionContextPlugin",
    "BrowserSessionProvider",
    "BrowserSessionSignal",
    "ContextKind",
    "FIELD_CLASSIFICATION",
    "MountKind",
    "MountedItem",
    "MountService",
    "RESTORE_PRIORITY",
    "RecoveryPriority",
    "RecoveryAction",
    "RecoveryActionStatus",
    "RecoveryActionType",
    "RecoveryExecutionService",
    "RecoveryExecutorRegistry",
    "RecoveryPlanner",
    "RecoveryReport",
    "WindowsDefaultOpenExecutor",
    "RestoreResult",
    "TrailCollector",
    "TrailEvent",
    "TrailStore",
]
