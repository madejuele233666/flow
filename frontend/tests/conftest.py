from __future__ import annotations

import importlib.util

_HAS_PYSIDE6 = importlib.util.find_spec("PySide6") is not None

if not _HAS_PYSIDE6:
    collect_ignore_glob = [
        "hud/test_payload_integrity.py",
        "hud/test_runtime_profiles.py",
        "hud/test_service_contract.py",
        "hud/test_widget_runtime.py",
        "hud/test_transition_runtime.py",
        "hud/test_lifecycle_runtime.py",
        "hud/test_task_flow_contract.py",
    ]


def pytest_report_header(config) -> str:
    if _HAS_PYSIDE6:
        return "PySide6 available: GUI HUD contract tests enabled"
    return 'PySide6 missing: GUI HUD tests require `pip install -e ".[dev,gui]"`'
