"""Test collection guards for optional test dependencies.

These tests rely on optional GUI/async plugins that may be unavailable in
minimal CI/dev environments.
"""

from __future__ import annotations

import importlib.util


def _has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


collect_ignore_glob: list[str] = []

if not _has_module("PySide6"):
    collect_ignore_glob.extend(
        [
            "hud/test_lifecycle_runtime.py",
            "hud/test_payload_integrity.py",
            "hud/test_service_contract.py",
            "hud/test_transition_runtime.py",
            "hud/test_widget_runtime.py",
        ]
    )

if not _has_module("pytest_asyncio"):
    collect_ignore_glob.append("hud/test_ipc_client_plugin.py")
