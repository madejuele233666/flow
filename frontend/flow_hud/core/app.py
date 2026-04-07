"""HUD app orchestrator with canonical transition/widget runtime boundaries."""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterable

from flow_hud.core.config import HudConfig
from flow_hud.core.events import HudBackgroundEventWorker, HudEventBus, HudEventType
from flow_hud.core.events_payload import (
    StateTransitionedPayload,
    WidgetRegisteredPayload,
    WidgetUnregisteredPayload,
)
from flow_hud.core.hooks import HudHookManager
from flow_hud.core.hooks_payload import AfterTransitionPayload, BeforeWidgetRegisterPayload, VetoTransitionPayload
from flow_hud.core.state_machine import HudState, HudStateMachine, can_transition
from flow_hud.core.widget_slots import ensure_valid_widget_slot
from flow_hud.plugins.context import (
    HudAdminContext,
    HudPluginContext,
    create_admin_context,
    create_plugin_context,
)
from flow_hud.plugins.registry import HudPluginRegistry

if TYPE_CHECKING:
    from flow_hud.runtime import RuntimePluginSpec

logger = logging.getLogger(__name__)


@dataclass
class _WidgetRegistration:
    name: str
    slot: str
    widget: Any | None
    owner: str | None
    source: str


class HudApp:
    """Top-level runtime orchestrator and canonical host boundary."""

    def __init__(self, config: HudConfig | None = None, *, discover_plugins: bool = True) -> None:
        self.config = config or HudConfig.load()

        self._bg_worker = HudBackgroundEventWorker(max_retries=self.config.worker_max_retries)
        self._bg_worker.start()
        self._runtime_thread_id = threading.get_ident()
        self._is_shutdown = False
        self._is_shutting_down = False

        self.event_bus = HudEventBus(background_worker=self._bg_worker)
        self.hook_manager = HudHookManager(
            hook_timeout=self.config.hook_timeout,
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout,
            safe_mode=self.config.safe_mode,
            dev_mode=self.config.dev_mode,
        )
        self.state_machine = HudStateMachine()
        self.plugins = HudPluginRegistry()

        self._widget_registry: dict[str, _WidgetRegistration] = {}
        self._owner_event_handlers: dict[str, list[tuple[Any, Callable]]] = defaultdict(list)
        self._owner_hook_implementors: dict[str, list[object]] = defaultdict(list)
        self._owner_widgets: dict[str, list[str]] = defaultdict(list)
        self._plugin_setup_order: list[str] = []
        self._plugin_setup_done: set[str] = set()
        self._admin_routing: dict[str, dict[str, bool]] = {}

        self.plugin_context = create_plugin_context(config=self.config, runtime=self)
        self.admin_context = create_admin_context(config=self.config, runtime=self)

        if discover_plugins and not self.config.safe_mode:
            self.plugins.discover()

    def setup_plugins(self, runtime_specs: Iterable["RuntimePluginSpec"] = ()) -> None:
        """Single lifecycle authority for profile + discovery plugin setup."""
        self._ensure_runtime_active("setup_plugins")
        self._ensure_runtime_thread("setup_plugins")
        profile_admin_routing: dict[str, bool] = {}
        profile_order: list[str] = []

        for spec in runtime_specs:
            plugin_class = spec.load_plugin_class()
            plugin_name = plugin_class.manifest.name
            if plugin_name in profile_admin_routing:
                logger.warning(
                    "ignoring duplicate runtime-profile plugin %r (keeping first accepted entry)",
                    plugin_name,
                )
                continue
            existing = self.plugins.get(plugin_name)
            if existing is None:
                self.plugins.register(plugin_class())
            elif type(existing) is not plugin_class:
                if plugin_name in self._plugin_setup_done:
                    logger.warning(
                        "ignoring runtime-profile replacement for already setup plugin %r",
                        plugin_name,
                    )
                else:
                    # Runtime profile is declarative authority for overlap resolution.
                    self.plugins.replace(plugin_class())
            profile_order.append(plugin_name)
            profile_admin_routing[plugin_name] = bool(spec.admin)

        setup_plan = list(profile_order)
        for plugin_name in sorted(self.plugins.names()):
            if plugin_name not in setup_plan:
                setup_plan.append(plugin_name)

        config_admin = set(self.config.admin_plugins)

        for plugin_name in setup_plan:
            if plugin_name in self._plugin_setup_done:
                continue

            plugin = self.plugins.get(plugin_name)
            if plugin is None:
                continue

            profile_admin = profile_admin_routing.get(plugin_name, False)
            config_admin_flag = plugin_name in config_admin
            is_admin = profile_admin or config_admin_flag
            conflict = profile_admin != config_admin_flag
            target_ctx = (
                self._admin_context_for_owner(plugin_name)
                if is_admin
                else self._plugin_context_for_owner(plugin_name)
            )
            self._admin_routing[plugin_name] = {
                "profile_admin": profile_admin,
                "config_admin": config_admin_flag,
                "final_admin": is_admin,
                "conflict": conflict,
                "resolved_by_merge": conflict,
            }

            try:
                plugin.setup(target_ctx)
            except Exception:
                logger.exception("plugin %r setup failed", plugin_name)
                try:
                    plugin.teardown()
                except Exception:
                    logger.exception("plugin %r teardown after setup failure failed", plugin_name)
                self._cleanup_owner(plugin_name)
                continue

            self._plugin_setup_done.add(plugin_name)
            self._plugin_setup_order.append(plugin_name)
            logger.info("plugin %r setup complete (admin=%s)", plugin_name, is_admin)

    def shutdown(self) -> None:
        self._ensure_runtime_thread("shutdown")
        if self._is_shutdown:
            return
        self._is_shutting_down = True
        logger.info("HudApp shutting down...")

        processed: set[str] = set()
        for plugin_name in reversed(self._plugin_setup_order):
            plugin = self.plugins.get(plugin_name)
            if plugin is not None:
                try:
                    plugin.teardown()
                except Exception:
                    logger.exception("plugin %r teardown failed", plugin_name)
            self._cleanup_owner(plugin_name)
            processed.add(plugin_name)

        remaining_owners = (
            set(self._owner_event_handlers.keys())
            | set(self._owner_hook_implementors.keys())
            | set(self._owner_widgets.keys())
        )
        for owner in remaining_owners:
            if owner not in processed:
                self._cleanup_owner(owner)

        self._plugin_setup_done.clear()
        self._plugin_setup_order.clear()
        self._drain_qt_events()
        self._bg_worker.stop()
        self._is_shutting_down = False
        self._is_shutdown = True
        logger.info("HudApp shutdown complete")

    def transition_to(self, target: str) -> dict[str, str]:
        """Canonical transition path used by service/context callers."""
        if self._is_shutting_down:
            raise ValueError("transition_to unavailable during shutdown")
        self._ensure_runtime_active("transition_to")
        self._ensure_runtime_thread("transition_to")
        try:
            target_state = HudState(target)
        except ValueError as exc:
            allowed = [s.value for s in HudState]
            raise ValueError(f"invalid target state: {target!r}; allowed: {allowed}") from exc

        current_state = self.state_machine.current_state
        if not can_transition(current_state, target_state):
            raise ValueError(f"illegal transition: {current_state.value} -> {target_state.value}")

        approved = self.hook_manager.call(
            "before_state_transition",
            VetoTransitionPayload(
                current_state=current_state.value,
                target_state=target_state.value,
            ),
        )
        if approved is False:
            raise ValueError(f"state transition vetoed: {self.state_machine.current_state.value} -> {target_state.value}")

        old_state, new_state = self.state_machine.transition(target_state)

        self.hook_manager.call(
            "on_after_state_transition",
            AfterTransitionPayload(old_state=old_state.value, new_state=new_state.value),
        )
        self.event_bus.emit(
            HudEventType.STATE_TRANSITIONED,
            StateTransitionedPayload(old_state=old_state.value, new_state=new_state.value),
        )
        return {"old_state": old_state.value, "new_state": new_state.value}

    def register_widget(
        self,
        name: str,
        slot: str,
        *,
        widget: Any | None,
        owner: str | None,
        source: str,
    ) -> dict[str, Any]:
        """Canonical widget registration path for plugin/service callers."""
        self._ensure_runtime_active("register_widget")
        self._ensure_runtime_thread("register_widget")
        if source not in {"plugin", "service"}:
            raise ValueError(f"invalid widget registration source: {source!r}")
        widget_name = str(name).strip()
        if not widget_name:
            raise ValueError("widget name cannot be empty")

        resolved_slot = ensure_valid_widget_slot(slot)

        if source == "plugin" and widget is None:
            raise ValueError("plugin widget registration requires a widget instance")
        if source == "plugin" and owner is None:
            raise ValueError("plugin widget registration requires owner")
        if source == "plugin" and widget is not None:
            from PySide6.QtWidgets import QWidget

            if not isinstance(widget, QWidget):
                raise ValueError("plugin widget registration requires a QWidget instance")
        if source == "service" and widget is not None:
            raise ValueError("service widget registration cannot include widget instance")
        if source == "service" and owner is not None:
            raise ValueError("service widget registration cannot include owner")

        rewritten = self.hook_manager.call(
            "before_widget_register",
            BeforeWidgetRegisterPayload(name=widget_name, slot=resolved_slot),
        )
        if rewritten is not None:
            resolved_slot = ensure_valid_widget_slot(rewritten.slot)

        previous = self._widget_registry.get(widget_name)
        if previous is not None and previous.owner is not None:
            self._remove_owner_widget(previous.owner, widget_name)

        self._widget_registry[widget_name] = _WidgetRegistration(
            name=widget_name,
            slot=resolved_slot,
            widget=widget,
            owner=owner,
            source=source,
        )

        if owner is not None:
            self._append_owner_widget(owner, widget_name)

        self.event_bus.emit(
            HudEventType.WIDGET_REGISTERED,
            WidgetRegisteredPayload(name=widget_name, slot=resolved_slot),
        )

        if source == "service":
            return {
                "name": widget_name,
                "slot": resolved_slot,
                "reserved": True,
                "mounted": False,
            }

        return {
            "name": widget_name,
            "slot": resolved_slot,
            "registered": True,
            # Mounting is event-driven and may happen later on the UI runtime.
            "mounted": False,
        }

    def unregister_widget(self, name: str) -> None:
        self._ensure_runtime_active("unregister_widget")
        self._ensure_runtime_thread("unregister_widget")
        record = self._widget_registry.pop(name, None)
        if record is None:
            return
        if record.owner is not None:
            self._remove_owner_widget(record.owner, name)
        self.event_bus.emit(
            HudEventType.WIDGET_UNREGISTERED,
            WidgetUnregisteredPayload(name=name),
        )

    def list_widget_mounts(self) -> list[tuple[str, Any, str]]:
        mounts: list[tuple[str, Any, str]] = []
        for record in self._widget_registry.values():
            if record.widget is None:
                continue
            mounts.append((record.name, record.widget, record.slot))
        return mounts

    def get_widget_mount(self, name: str) -> tuple[Any, str] | None:
        record = self._widget_registry.get(name)
        if record is None or record.widget is None:
            return None
        return (record.widget, record.slot)

    def subscribe_event(self, event_type: Any, handler: Callable, *, owner: str | None) -> None:
        self._ensure_runtime_active("subscribe_event")
        self._ensure_runtime_thread("subscribe_event")
        if owner is None:
            raise ValueError("subscribe_event requires owner")
        self.event_bus.subscribe(event_type, handler)
        if owner is not None:
            self._owner_event_handlers[owner].append((event_type, handler))

    def unsubscribe_event(self, event_type: Any, handler: Callable, *, owner: str | None) -> None:
        self._ensure_runtime_active("unsubscribe_event")
        self._ensure_runtime_thread("unsubscribe_event")
        if owner is None:
            raise ValueError("unsubscribe_event requires owner")
        self.event_bus.unsubscribe(event_type, handler)
        entries = self._owner_event_handlers.get(owner)
        if not entries:
            return
        for idx, pair in enumerate(entries):
            if pair == (event_type, handler):
                entries.pop(idx)
                break

    def emit_event(self, event_type: Any, payload: Any = None) -> None:
        if self._is_shutting_down:
            raise ValueError("emit_event unavailable during shutdown")
        self._ensure_runtime_active("emit_event")
        self.event_bus.emit(event_type, payload)

    def emit_background_event(self, event_type: Any, payload: Any = None) -> None:
        if self._is_shutting_down:
            raise ValueError("emit_background_event unavailable during shutdown")
        self._ensure_runtime_active("emit_background_event")
        self.event_bus.emit_background(event_type, payload)

    def register_hook(self, implementor: object, *, owner: str | None) -> list[str]:
        self._ensure_runtime_active("register_hook")
        self._ensure_runtime_thread("register_hook")
        if owner is None:
            raise ValueError("register_hook requires owner")
        registered = self.hook_manager.register(implementor)
        if owner is not None and registered and not any(x is implementor for x in self._owner_hook_implementors[owner]):
            self._owner_hook_implementors[owner].append(implementor)
        return registered

    def unregister_hook(self, implementor: object, *, owner: str | None) -> None:
        self._ensure_runtime_active("unregister_hook")
        self._ensure_runtime_thread("unregister_hook")
        if owner is None:
            raise ValueError("unregister_hook requires owner")
        self.hook_manager.unregister(implementor)
        entries = self._owner_hook_implementors.get(owner)
        if not entries:
            return
        self._owner_hook_implementors[owner] = [x for x in entries if x is not implementor]

    def current_state_value(self) -> str:
        return self.state_machine.current_state.value

    def active_plugin_names(self) -> list[str]:
        if self._is_shutdown:
            return []
        return list(self._plugin_setup_order)

    def admin_routing_records(self) -> dict[str, dict[str, bool]]:
        return {
            name: dict(record)
            for name, record in self._admin_routing.items()
        }

    def _plugin_context_for_owner(self, owner: str) -> HudPluginContext:
        return create_plugin_context(config=self.config, runtime=self, owner=owner)

    def _admin_context_for_owner(self, owner: str) -> HudAdminContext:
        return create_admin_context(config=self.config, runtime=self, owner=owner)

    def _cleanup_owner(self, owner: str) -> None:
        for event_type, handler in reversed(self._owner_event_handlers.pop(owner, [])):
            self.event_bus.unsubscribe(event_type, handler)

        for implementor in reversed(self._owner_hook_implementors.pop(owner, [])):
            self.hook_manager.unregister(implementor)

        for widget_name in reversed(self._owner_widgets.pop(owner, [])):
            self.unregister_widget(widget_name)

    def _ensure_runtime_thread(self, operation: str) -> None:
        if threading.get_ident() != self._runtime_thread_id:
            raise ValueError(f"{operation} must run on HUD runtime thread")

    def _ensure_runtime_active(self, operation: str) -> None:
        if self._is_shutdown:
            raise ValueError(f"{operation} unavailable after shutdown")

    @staticmethod
    def _drain_qt_events() -> None:
        try:
            from PySide6.QtWidgets import QApplication
        except Exception:
            return

        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def _append_owner_widget(self, owner: str, name: str) -> None:
        entries = self._owner_widgets[owner]
        if name in entries:
            entries.remove(name)
        entries.append(name)

    def _remove_owner_widget(self, owner: str, name: str) -> None:
        entries = self._owner_widgets.get(owner)
        if not entries:
            return
        try:
            entries.remove(name)
        except ValueError:
            return
