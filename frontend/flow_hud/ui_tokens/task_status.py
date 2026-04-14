from __future__ import annotations

TASK_STATUS_LAYOUT_MARGINS = (16, 14, 16, 14)
TASK_STATUS_LAYOUT_SPACING = 6
TASK_STATUS_EMPTY_TITLE = "Flow is ready"
TASK_STATUS_EMPTY_STATE = "No active task"
TASK_STATUS_OFFLINE_TITLE = "Flow daemon unavailable"
TASK_STATUS_OFFLINE_STATE = "Backend offline"
TASK_STATUS_FOCUS_TIMER_PENDING_TEXT = "Focus timer pending"
TASK_STATUS_BREAK_SUGGESTED_TEXT = "Break suggested"
TASK_STATUS_EMPTY_META_TEXT = "Start a task to populate the HUD."
TASK_STATUS_OFFLINE_META_TEXT = "Start the daemon to restore task updates."
TASK_STATUS_STYLE = """
QFrame#task-status-card {
    background-color: rgba(18, 24, 35, 220);
    border: 1px solid rgba(126, 155, 191, 120);
    border-radius: 14px;
}
QLabel#task-status-state {
    color: rgba(167, 197, 255, 230);
    font-size: 12px;
    font-family: 'Segoe UI';
    font-weight: 600;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}
QLabel#task-status-title {
    color: rgba(245, 247, 250, 245);
    font-size: 18px;
    font-family: 'Segoe UI';
    font-weight: 600;
}
QLabel#task-status-meta {
    color: rgba(197, 208, 224, 230);
    font-size: 12px;
    font-family: 'Segoe UI';
}
QLabel#task-status-badge {
    color: rgba(64, 33, 4, 230);
    background-color: rgba(255, 210, 128, 235);
    border-radius: 10px;
    padding: 3px 8px;
    font-size: 11px;
    font-family: 'Segoe UI';
    font-weight: 700;
}
"""


def task_status_meta_text(mode: str) -> str:
    if mode == "empty":
        return TASK_STATUS_EMPTY_META_TEXT
    if mode == "offline":
        return TASK_STATUS_OFFLINE_META_TEXT
    return ""


def format_task_status_duration(duration_min: int | None) -> str:
    if duration_min is None:
        return TASK_STATUS_FOCUS_TIMER_PENDING_TEXT
    return f"{duration_min} min focus"
