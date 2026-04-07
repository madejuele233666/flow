"""HUD plugin sandbox contexts with owner-aware runtime registration."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from flow_hud.core.config import HudConfig

from flow_hud.core.events import HudEventType

_HOST_OWNED_EVENTS = {
    HudEventType.STATE_TRANSITIONED,
    HudEventType.WIDGET_REGISTERED,
    HudEventType.WIDGET_UNREGISTERED,
}


@runtime_checkable
class HudEventBusRegistrar(Protocol):
    def subscribe(self, event_type: Any, handler: Callable) -> None: ...
    def unsubscribe(self, event_type: Any, handler: Callable) -> None: ...
    def emit(self, event_type: Any, payload: Any = None) -> None: ...
    def emit_background(self, event_type: Any, payload: Any = None) -> None: ...


@runtime_checkable
class HudRuntimeGateway(Protocol):
    def subscribe_event(self, event_type: Any, handler: Callable, *, owner: str | None) -> None: ...
    def unsubscribe_event(self, event_type: Any, handler: Callable, *, owner: str | None) -> None: ...
    def emit_event(self, event_type: Any, payload: Any = None) -> None: ...
    def emit_background_event(self, event_type: Any, payload: Any = None) -> None: ...

    def register_hook(self, implementor: object, *, owner: str | None) -> list[str]: ...
    def unregister_hook(self, implementor: object, *, owner: str | None) -> None: ...

    def register_widget(
        self,
        name: str,
        slot: str,
        *,
        widget: Any | None,
        owner: str | None,
        source: str,
    ) -> dict[str, Any]: ...

    def transition_to(self, target: str) -> dict[str, str]: ...
    def current_state_value(self) -> str: ...


class _PluginRuntimeGatewayFacade:
    """Narrow runtime gateway that hides host internals from plugin contexts."""

    __slots__ = (
        "_subscribe_event",
        "_unsubscribe_event",
        "_emit_event",
        "_emit_background_event",
        "_register_hook",
        "_unregister_hook",
        "_register_widget",
    )

    def __init__(self, runtime: HudRuntimeGateway) -> None:
        self._subscribe_event = runtime.subscribe_event
        self._unsubscribe_event = runtime.unsubscribe_event
        self._emit_event = runtime.emit_event
        self._emit_background_event = runtime.emit_background_event
        self._register_hook = runtime.register_hook
        self._unregister_hook = runtime.unregister_hook
        self._register_widget = runtime.register_widget

    def subscribe_event(self, event_type: Any, handler: Callable, *, owner: str | None) -> None:
        self._subscribe_event(event_type, handler, owner=owner)

    def unsubscribe_event(self, event_type: Any, handler: Callable, *, owner: str | None) -> None:
        self._unsubscribe_event(event_type, handler, owner=owner)

    def emit_event(self, event_type: Any, payload: Any = None) -> None:
        self._emit_event(event_type, payload)

    def emit_background_event(self, event_type: Any, payload: Any = None) -> None:
        self._emit_background_event(event_type, payload)

    def register_hook(self, implementor: object, *, owner: str | None) -> list[str]:
        return self._register_hook(implementor, owner=owner)

    def unregister_hook(self, implementor: object, *, owner: str | None) -> None:
        self._unregister_hook(implementor, owner=owner)

    def register_widget(
        self,
        name: str,
        slot: str,
        *,
        widget: Any | None,
        owner: str | None,
        source: str,
    ) -> dict[str, Any]:
        return self._register_widget(
            name=name,
            slot=slot,
            widget=widget,
            owner=owner,
            source=source,
        )


class _AdminRuntimeGatewayFacade(_PluginRuntimeGatewayFacade):
    __slots__ = ("_transition_to", "_current_state_value")

    def __init__(self, runtime: HudRuntimeGateway) -> None:
        super().__init__(runtime)
        self._transition_to = runtime.transition_to
        self._current_state_value = runtime.current_state_value

    def transition_to(self, target: str) -> dict[str, str]:
        return self._transition_to(target)

    def current_state_value(self) -> str:
        return self._current_state_value()


class _OwnedEventBusView:
    def __init__(self, runtime: _PluginRuntimeGatewayFacade, owner: str | None) -> None:
        self._runtime = runtime
        self._owner = owner

    def _require_owner(self) -> str:
        if self._owner is None:
            raise ValueError("owner-scoped context required")
        return self._owner

    def subscribe(self, event_type: Any, handler: Callable) -> None:
        self._runtime.subscribe_event(event_type, handler, owner=self._require_owner())

    def unsubscribe(self, event_type: Any, handler: Callable) -> None:
        self._runtime.unsubscribe_event(event_type, handler, owner=self._require_owner())

    def emit(self, event_type: Any, payload: Any = None) -> None:
        self._ensure_plugin_event_allowed(event_type)
        self._runtime.emit_event(event_type, payload)

    def emit_background(self, event_type: Any, payload: Any = None) -> None:
        self._ensure_plugin_event_allowed(event_type)
        self._runtime.emit_background_event(event_type, payload)

    @staticmethod
    def _ensure_plugin_event_allowed(event_type: Any) -> None:
        if event_type in _HOST_OWNED_EVENTS:
            raise ValueError("plugin context cannot emit host-owned lifecycle events")


class HudPluginContext:
    """Standard plugin sandbox with owner-aware registration APIs."""

    def __init__(
        self,
        *,
        config: HudConfig,
        runtime: HudRuntimeGateway | _PluginRuntimeGatewayFacade,
        owner: str | None = None,
    ) -> None:
        self._config = config
        if isinstance(runtime, _PluginRuntimeGatewayFacade):
            self.__runtime_gateway = runtime
        else:
            self.__runtime_gateway = _PluginRuntimeGatewayFacade(runtime)
        self._owner = owner
        self._event_bus_view = _OwnedEventBusView(runtime=self.__runtime_gateway, owner=owner)

    @property
    def owner(self) -> str | None:
        return self._owner

    @property
    def event_bus(self) -> HudEventBusRegistrar:
        return self._event_bus_view

    def _require_owner(self) -> str:
        if self._owner is None:
            raise ValueError("owner-scoped context required")
        return self._owner

    def subscribe_event(self, event_type: Any, handler: Callable) -> None:
        self.__runtime_gateway.subscribe_event(event_type, handler, owner=self._require_owner())

    def unsubscribe_event(self, event_type: Any, handler: Callable) -> None:
        self.__runtime_gateway.unsubscribe_event(event_type, handler, owner=self._require_owner())

    def register_widget(self, name: str, widget: Any, *, slot: str = "center") -> dict[str, Any]:
        return self.__runtime_gateway.register_widget(
            name=name,
            slot=slot,
            widget=widget,
            owner=self._require_owner(),
            source="plugin",
        )

    def register_hook(self, implementor: object) -> list[str]:
        return self.__runtime_gateway.register_hook(implementor, owner=self._require_owner())

    def unregister_hook(self, implementor: object) -> None:
        self.__runtime_gateway.unregister_hook(implementor, owner=self._require_owner())

    def get_extension_config(self, plugin_name: str) -> dict[str, Any]:
        return copy.deepcopy(self._config.extensions.get(plugin_name, {}))

    def get_connection_config(self) -> dict[str, Any]:
        return {
            "transport": self._config.connection_transport,
            "host": self._config.connection_host,
            "port": self._config.connection_port,
            "socket_path": self._config.connection_socket_path,
        }

    def get_ipc_client_config(self) -> dict[str, Any]:
        return {
            "thread_join_timeout_s": self._config.ipc_thread_join_timeout_s,
            "retry_initial_backoff_s": self._config.ipc_retry_initial_backoff_s,
            "retry_max_backoff_s": self._config.ipc_retry_max_backoff_s,
            "retry_backoff_multiplier": self._config.ipc_retry_backoff_multiplier,
            "retry_backoff_jitter_ratio": self._config.ipc_retry_backoff_jitter_ratio,
            "retry_error_sleep_s": self._config.ipc_retry_error_sleep_s,
            "stop_poll_interval_s": self._config.ipc_stop_poll_interval_s,
            "rpc_capabilities": list(self._config.ipc_rpc_capabilities),
            "push_capabilities": list(self._config.ipc_push_capabilities),
        }

    @property
    def data_dir(self) -> Path:
        return self._config.data_dir

    @property
    def safe_mode(self) -> bool:
        return self._config.safe_mode


class HudAdminContext(HudPluginContext):
    """Admin sandbox with read-only state metadata and canonical transition API."""

    def __init__(
        self,
        *,
        config: HudConfig,
        runtime: HudRuntimeGateway | _AdminRuntimeGatewayFacade,
        owner: str | None = None,
    ) -> None:
        if isinstance(runtime, _AdminRuntimeGatewayFacade):
            admin_runtime = runtime
        else:
            admin_runtime = _AdminRuntimeGatewayFacade(runtime)
        super().__init__(config=config, runtime=admin_runtime, owner=owner)

    def request_transition(self, target: str) -> dict[str, str]:
        return self._HudPluginContext__runtime_gateway.transition_to(target)

    @property
    def current_state(self) -> str:
        return self._HudPluginContext__runtime_gateway.current_state_value()
