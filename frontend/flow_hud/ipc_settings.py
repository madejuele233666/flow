"""Shared IPC client defaults and tuning parser for HUD."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_CONNECTION_TRANSPORT = "tcp"
DEFAULT_CONNECTION_HOST = "127.0.0.1"
DEFAULT_CONNECTION_PORT = 54321


@dataclass(frozen=True)
class IpcClientTuning:
    thread_join_timeout_s: float = 5.0
    retry_initial_backoff_s: float = 0.2
    retry_max_backoff_s: float = 2.0
    retry_backoff_multiplier: float = 1.5
    retry_backoff_jitter_ratio: float = 0.1
    retry_error_sleep_s: float = 1.0
    stop_poll_interval_s: float = 0.1
    rpc_capabilities: tuple[str, ...] = ()
    push_capabilities: tuple[str, ...] = ("push.timer",)


def parse_ipc_client_tuning(defaults: dict[str, Any], overrides: dict[str, Any]) -> IpcClientTuning:
    """Build immutable IPC tuning from defaults + plugin overrides."""

    merged: dict[str, Any] = dict(defaults)
    merged.update(overrides)
    fallback = IpcClientTuning()

    return IpcClientTuning(
        thread_join_timeout_s=_as_positive_float(merged.get("thread_join_timeout_s"), fallback.thread_join_timeout_s),
        retry_initial_backoff_s=_as_positive_float(
            merged.get("retry_initial_backoff_s"),
            fallback.retry_initial_backoff_s,
        ),
        retry_max_backoff_s=_as_positive_float(merged.get("retry_max_backoff_s"), fallback.retry_max_backoff_s),
        retry_backoff_multiplier=_as_positive_float(
            merged.get("retry_backoff_multiplier"),
            fallback.retry_backoff_multiplier,
        ),
        retry_backoff_jitter_ratio=_as_non_negative_float(
            merged.get("retry_backoff_jitter_ratio"),
            fallback.retry_backoff_jitter_ratio,
        ),
        retry_error_sleep_s=_as_positive_float(merged.get("retry_error_sleep_s"), fallback.retry_error_sleep_s),
        stop_poll_interval_s=_as_positive_float(merged.get("stop_poll_interval_s"), fallback.stop_poll_interval_s),
        rpc_capabilities=_as_string_tuple(merged.get("rpc_capabilities"), fallback.rpc_capabilities, allow_empty=True),
        push_capabilities=_as_string_tuple(
            merged.get("push_capabilities"),
            fallback.push_capabilities,
            allow_empty=True,
        ),
    )


def _as_positive_float(raw: Any, fallback: float) -> float:
    try:
        value = float(raw)
    except Exception:
        return fallback
    if value <= 0:
        return fallback
    return value


def _as_non_negative_float(raw: Any, fallback: float) -> float:
    try:
        value = float(raw)
    except Exception:
        return fallback
    if value < 0:
        return fallback
    return value


def _as_string_tuple(raw: Any, fallback: tuple[str, ...], *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(raw, list):
        return fallback
    values = tuple(item for item in raw if isinstance(item, str) and item)
    if values or allow_empty:
        return values
    return fallback
