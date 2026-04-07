"""Canonical widget slot contract for HUD runtime."""

from __future__ import annotations

VALID_WIDGET_SLOTS = frozenset({
    "top_left",
    "top_right",
    "center",
    "bottom_left",
    "bottom_right",
})


def normalize_widget_slot(slot: str) -> str:
    value = str(slot).strip().lower()
    if not value:
        raise ValueError("widget slot cannot be empty")
    return value


def ensure_valid_widget_slot(slot: str) -> str:
    value = normalize_widget_slot(slot)
    if value not in VALID_WIDGET_SLOTS:
        allowed = ", ".join(sorted(VALID_WIDGET_SLOTS))
        raise ValueError(f"invalid widget slot: {slot!r}; allowed: {allowed}")
    return value
