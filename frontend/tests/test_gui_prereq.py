from __future__ import annotations

import importlib.util

import pytest


def test_pyside6_gui_prerequisite() -> None:
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip('PySide6 prerequisite missing; install `pip install -e ".[dev,gui]"` to run GUI HUD tests')
