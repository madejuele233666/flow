## MODIFIED Requirements

### Requirement: 模块化沙盒与插件上下文 (Plugin Context & Sandbox)
HUD 的具体能力（网络通信、雷达监测、渲染画板）必须通过继承 `HookBasePlugin` 此类的插件模式接入。核心引擎为其发放限制性的 `PluginContext` (包含 `EventBus`，配置源和 `Hooks` 入口)，防止插件做无法追溯的跨域访问。为确保插件注册和解绑过程的安全，`Hooks` 入口对象必须遵循强类型的 `Protocol`（如 `HookRegistrarProtocol`），严禁将其作为 `Any` 传递，以支持静态类型验证和自动补全。

#### Scenario: 插件规范订阅事件
- **WHEN** 当 `VisualPlugin` (视觉渲染插件) 在 `setup(ctx)` 执行期间。
- **THEN** 插件只能通过 `ctx.event_bus.subscribe(EventType.STATE_CHANGED, self.draw)` 或 `ctx.register_hook(self)` 进行合理合法地监听，而非通过自己 import 其他包拿到实例强行绑定。这些接口的参数受到强类型系统的严格检查保障，以杜绝因类型疏忽引起的运行期注册崩溃。这是防腐层的核心所在。
