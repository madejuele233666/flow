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
HUD 插件系统 MUST 通过受限上下文暴露能力，并且关键运行时操作（状态迁移、组件注册）必须进入宿主定义的规范化管线，禁止插件或服务层绕过宿主直接触发底层状态变更。

#### Scenario: 插件遵循规范化运行时边界
- **WHEN** 插件在 `setup(ctx)` 中接入状态或组件能力
- **THEN** 插件通过 `ctx` 暴露的受控 API 进入宿主管线
- **AND** 不允许通过直接访问底层状态机实例绕过 lifecycle hooks/events。

#### Scenario: Admin 插件无直连转移逃逸
- **WHEN** admin 插件需要请求状态变化
- **THEN** 只能调用宿主提供的规范化 transition API
- **AND** 不存在可公开调用的 `state_machine.transition(...)` 直通路径。

### Requirement: UI 微件化组合机制 (Sub-Widgets as Plugins)
HUD 插件组件组合 MUST 使用 slot-aware 的宿主组合管线，并以宿主注册表为唯一真相源，不得依赖仅本地字典或一次性启动快照挂载。

#### Scenario: 组件经由 slot 策略挂载
- **WHEN** 视觉插件注册组件到命名 slot
- **THEN** 宿主执行 `before_widget_register`、持久化注册记录、发出注册事件并按 slot 策略挂载
- **AND** 后续动态注册也会进入同一组合路径。

### Requirement: 插件防出错隔离 (Fault-Tolerant execution)
插件系统 MUST 在 setup、hook 执行、teardown 和清理阶段提供故障隔离，并保持宿主可继续运行和收敛关闭。

#### Scenario: setup 或 hook 异常隔离
- **WHEN** 某插件 setup 或 hook 抛出异常
- **THEN** 异常被隔离记录，不导致宿主整体崩溃
- **AND** 其他插件生命周期可继续推进。

#### Scenario: teardown 异常后宿主仍可清理
- **WHEN** 某插件 teardown 抛出异常
- **THEN** 宿主继续执行剩余插件 teardown 和宿主侧注册清理
- **AND** 不因单插件故障中断全局 shutdown。

#### Scenario: 宿主按 owner 清理注册痕迹
- **WHEN** 宿主进入 shutdown 或插件卸载
- **THEN** hook/event/widget 注册项按 owner 归属被回收
- **AND** 清理不依赖插件主动反注册。
