# 心流引擎 (Flow Engine)

**心流引擎** 是一个极简、自律且充满黑客（Geek）风格的终端任务管理与生产力系统。它基于 **严格的单一任务独占（Single-Tasking）** 协议设计，致力于用严苛的逻辑流转消除因多任务切换带来的认知损耗与现代职业焦虑。

---

## ✨ 核心特性矩阵

### 1. 严格防打扰的八维状态机
系统内置了严格的任务八维状态模型：`Draft` → `Ready` → `Scheduled` → `In Progress` → `Paused` → `Blocked` → `Done` → `Canceled`。
*   **唯一排他原则**：系统在物理级别限制同时只能有一个任务处于 `In Progress` 状态。
*   **自动压栈机制**：当你强制开启新任务时，系统会自动将当前活跃任务转入 `Paused`（暂停）状态。

### 2. 六边形架构与端对端解耦 (Phase 4.6+)
经历过深度的架构重构，这套系统具有极佳的工程美学：
*   **六边形架构**：核心业务逻辑通过 `FlowClient` 端口协议与外部接口（CLI/TUI/HUD）交互，实现彻底解耦。
*   **端口防泄漏协议**：所有服务返回值均经过严格的原始类型映射（Primitive-Only），确保领域对象与 Qt 等第三方库不泄漏至外部调用方。
*   **高并发异步 I/O**：基于 `asyncio` 和 `httpx` 构建的 IPC 通信机制，大幅提升读写性能。

### 3. 多重交互态：HUD、TUI 与命令行
摒弃臃肿的主窗口，采用无感存在的"多维度交互"体验：
*   **桌面 HUD (Heads-Up Display)**：基于 PySide6 构建的半透明、非侵入式悬浮面板，支持三态（Ghost/Pulse/Command）交互逻辑。
*   **沉浸式 TUI**：内置基于 Textual 的命令行全屏监控面板，适合长期沉浸在代码或终端中的开发者。
*   **强力 CLI**：通过 `flow` 指令全局调度。

### 4. Markdown + Git 纯文本持久化
完全抛弃了笨重的关系型数据库。所有任务树、优先级信息均以标准的 `tasks.md` 持久化存储。
*   **Git 时光机**：配合 Ghost Daemon 守护进程，任何状态流转都会在后台自动触发 `git commit`。实现时光机级别的防灾回滚以及跨设备的私有云同步。

### 5. 强类型插件与钩子系统
系统架构了受 Pluggy 启发的 **强类型钩子框架 (Typed Hooks)**：
*   **熔断保护**：插件异常时自动熔断，确保核心流程永不崩溃。
*   **现场捕捉**：支持针对特定软件（如 VS Code、浏览器）的“现场捕捉插件”，在任务切换时自动捕获路径，并在任务恢复时一键复现。

### 6. AI 任务降维 (BYOK)
*   **BYOK 接入**：允许填入自定义 AI API Key，通过 `flow breakdown` 命令，让大模型瞬间将复杂任务拆解为 15 分钟级别的小步骤。

---

## 🛠️ CLI 指令集参考

你将通过 `flow` 终端指令作为入口与心流引擎交互：

### 核心流转指令
```bash
flow add "任务名称" --ddl "2026-10-01" --p 1   # 添加新任务
flow ls                   # 打印按“引力得分”排序的高优任务列表
flow start <TaskID>       # 核心魔法：打断当前任务 -> 自动压栈并触发快照 -> 启动新任务 -> 自动 Git 提交
flow status               # 查看当前的心流专注状态及已专注时长
flow block <TaskID> --reason "等待审批"   # 将任务标记为因外部依赖卡住
flow pause                # 主动暂停当前任务
flow resume <TaskID>      # 恢复暂停/阻塞中的任务
flow done                 # 完成当前活跃任务并归档
```

### 界面与服务管理
```bash
flow tui                  # 启动沉浸式终端监控面板 (TUI)
flow daemon start         # 在后台启动 Ghost Daemon 常驻进程 (IPC 服务)
flow daemon stop          # 停止后台运行的进程
flow daemon status        # 查看守护进程是否在线
python -m flow_hud.main    # 启动桌面 HUD 悬浮面板 (正在集成至 CLI)
```

### 智能与高阶命令
```bash
flow breakdown <TaskID>   # 让 AI 帮你把任务拆解成步骤
flow plugins ls           # 查看系统中已安装的外挂插件
flow export --format json # 导出当前的任务库数据
```

---

## 🚀 未来战略 (Roadmap)

我们正致力于在 `V2.0` 重塑更多可能：
1.  **MCP (Model Context Protocol) 彻底打通**：将心流引擎升级为 MCP 服务器。允许你的全局 AI（如 Claude Desktop）直接与当前的专注环境互动，交接任务物理上下文。
2.  **本地 RAG 专属记忆胶囊**：当你在一项任务上专注时，静默将你的查阅痕迹转化为任务专属向量数据库，为日后跨期工作恢复提供 AI 即时回溯。
3.  **万能通讯网关**：接入 Telegram/WeChat，通过对话即时捕捉灵感并直达本地任务库。

---

> *"用严苛的协议包裹思维，以无感的机制守护专注。"*

