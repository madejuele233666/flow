## ADDED Requirements

### Requirement: Standardize HUD Communication Port (RPC-ready)
HUD 必须定义一个标准的 `HudServiceProtocol`，所有方法必须仅接受内置基本类型（int, str, dict, list），并返回纯数据结构（dict 或 list[dict]）。

#### Scenario: Querying HUD State via Service
- **WHEN** 调用 `service.get_status()`
- **THEN** 返回一个 `dict`，包含 `state` (str) 和 `active_plugins` (list[str])，不含任何领域对象。

#### Scenario: State Transition via Service
- **WHEN** 调用 `service.transition_to("pulse")`
- **THEN** 返回一个 `dict`，包含 `old_state` (str) 和 `new_state` (str)。
