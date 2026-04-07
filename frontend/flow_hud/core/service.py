"""HUD service boundary that exposes canonical runtime semantics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from flow_hud.core.app import HudApp


@runtime_checkable
class HudServiceProtocol(Protocol):
    def get_status(self) -> dict[str, Any]: ...
    def transition_to(self, target: str) -> dict[str, Any]: ...
    def register_widget(self, name: str, slot: str) -> dict[str, Any]: ...
    def list_plugins(self) -> list[dict[str, Any]]: ...


class HudLocalService:
    def __init__(self, app: HudApp) -> None:
        self._app = app

    def get_status(self) -> dict[str, Any]:
        return {
            "state": self._app.current_state_value(),
            "active_plugins": self._app.active_plugin_names(),
            "safe_mode": self._app.config.safe_mode,
            "data_dir": str(self._app.config.data_dir),
        }

    def transition_to(self, target: str) -> dict[str, Any]:
        return self._app.transition_to(target)

    def register_widget(self, name: str, slot: str) -> dict[str, Any]:
        return self._app.register_widget(
            name=name,
            slot=slot,
            widget=None,
            owner=None,
            source="service",
        )

    def list_plugins(self) -> list[dict[str, Any]]:
        result = []
        for plugin_name in self._app.active_plugin_names():
            plugin = self._app.plugins.get(plugin_name)
            if plugin is None:
                continue
            result.append(
                {
                    "name": plugin.manifest.name,
                    "version": plugin.manifest.version,
                    "description": plugin.manifest.description,
                }
            )
        return result
