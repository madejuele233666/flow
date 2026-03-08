---
format: spec
version: 1.0.0
title: "Plugin System"
status: active
---

## Purpose
TBD

## Requirements

### Requirement: 模块化沙盒与插件上下文 (Plugin Context & Sandbox)
HUD 的具体能力（网络通信、雷达监测、渲染画板）必须通过继承 `HookBasePlugin` 此类的插件模式接入。核心引擎为其发放限制性的 `PluginContext` (包含 `EventBus`，配置源和 `Hooks` 入口)，防止插件做无法追溯的跨域访问。为确保插件注册和解绑过程的安全，`Hooks` 入口对象必须遵循强类型的 `Protocol`（如 `HookRegistrarProtocol`），严禁将其作为 `Any` 传递，以支持静态类型验证和自动补全。

#### Scenario: 插件规范订阅事件
- **WHEN** 当 `VisualPlugin` (视觉渲染插件) 在 `setup(ctx)` 执行期间。
- **THEN** 插件只能通过 `ctx.event_bus.subscribe(EventType.STATE_CHANGED, self.draw)` 或 `ctx.register_hook(self)` 进行合理合法地监听，而非通过自己 import 其他包拿到实例强行绑定。这些接口的参数受到强类型系统的严格检查保障，以杜绝因类型疏忽引起的运行期注册崩溃。这是防腐层的核心所在。

### Requirement: UI 微件化组合机制 (Sub-Widgets as Plugins)
区别于传统的单例庞大视图，主控 UI 画布作为一个简单的无边框透明 `QMainWindow`。提供接口允许外设“图形插件”向画布某个坐标系、层级 (`Z-index`) 或布局槽口注册自定义 `QWidget` 碎片。

#### Scenario: 按需组装视觉部件
- **WHEN** 一个专注于番茄钟功能的 `PomodoroUIPlugin` 初始化时，它向 Canvas 请求 `ctx.ui.register_widget('top_right', PomodoroWidget())`。
- **THEN** 插件系统能在隔离逻辑的同时，将这个图形部件安全合并显示进 HUD 的指定版图块。

### Requirement: 插件防出错隔离 (Fault-Tolerant execution)
使用主程序类似机制的 `HookManager` 带有熔断器。当某个逻辑插件抛出异常。必须阻止异常崩溃蔓延至事件中心。

#### Scenario: 某渲染插件偶发崩溃不死机
- **WHEN** 自定义的某个 UI 插件在响应重绘事件时遭遇了 `ValueError` 导致内部方法奔溃。
- **THEN** `EventBus/Hooks` 包裹的执行器会截获此异常做错误级别 Log，但保证整个 HUD App 依然持续工作响应后台。
