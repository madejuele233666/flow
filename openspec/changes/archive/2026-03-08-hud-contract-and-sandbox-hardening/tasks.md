## 1. [CORE] 端口层强化 (HudServiceProtocol)

- [x] 1.1 完善 `flow_hud/core/service.py` 中的 `HudServiceProtocol` 和 `HudLocalService`。
  【防腐规定】该文件 MUST NOT import 任何领域外部或 UI 组件（例如 `PySide6`、内部领域特型），接口入参出参仅允许基础类型。
- [x] 1.2 在 `flow_hud/core/service.py` 中的 `HudLocalService` 实现将状态和实体列表「剥皮」转字典的隔离逻辑。
  【防腐规定】该文件 MUST NOT 将内部如 `HudState` 枚举等对象直接丢入返回字典。
- [x] 1.3 实现测试 `tests/core/test_service.py` 覆盖验证 `HudLocalService` 调用的抗泄漏特性。
- [x] 1.4 【检查点】Present test log of `test_service.py` to user.
  MUST obtain explicit user confirmation before proceeding to next phase.

## 2. [CORE] 插件沙盒类型化 (Typed Context)

- [x] 2.1 定义 `flow_hud/plugins/context.py` 中的 `HudEventBusRegistrar` 与 `HudStateMachineProtocol`。
  【防腐规定】This file MUST NOT import `HudEventBus` 或 `HudStateMachine` 具体实体类以避免循环引用，必须通过 `TYPE_CHECKING` 或 `Any` 隔离。
- [x] 2.2 在 `flow_hud/plugins/context.py` 将 `HudPluginContext`/`HudAdminContext` 的 `event_bus` 等初始化注解替换为相应的 Protocol。
- [x] 2.3 【检查点】Present `mypy flow_hud/plugins/context.py` run output/type check to user.
  MUST obtain explicit user confirmation before proceeding to next phase.

## 3. [CORE] 载荷完整性与安全性加固 (Payload Integrity)

- [x] 3.1 在 `flow_hud/core/events_payload.py` 中，强制为所有 Event 数据载荷标注 `@dataclass(frozen=True)`。
- [x] 3.2 在 `flow_hud/core/hooks_payload.py` 中，明确 Waterfall 使用 `@dataclass`，而 Bail/Parallel 使用 `@dataclass(frozen=True)`。
- [x] 3.3 修改 `flow_hud/core/events.py` 中的 `HudEventBus.emit()`，增加代码显式进行 `is_dataclass` 及 `is_frozen` 检测，抛出 `TypeError` 阻拦违规传递。
- [x] 3.4 修改 `flow_hud/core/hooks.py` 中的 `HudHookManager.call()`，增加对应的类型强制断言。
- [x] 3.5 【检查点】Present the payloads audit & hook error handling test output to user.
  MUST obtain explicit user confirmation before proceeding to next phase.
