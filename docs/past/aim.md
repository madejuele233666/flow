# 心流引擎 (Flow Engine) - 终极全量特性白皮书

## 一、 MVP 核心特性矩阵 (Current Feature Set)

###### 1. 物理层：插件化现场捕捉系统 (Modular Context Plugins)

这是软件连接虚拟任务与物理桌面的桥梁，采用"核心引擎 + 扩展插件"的开放架构。

## **系统级快照与时光倒流**：在任务 Paused 或切换时，系统静默抓取当前活跃窗口的路径、URL 及坐标。当任务切回 In Progress，一键还原打断前的桌面排布。

**官方基础插件包 (First-party Bundles)**：内置对系统底层 API、主流浏览器（Chrome/Edge）和文件管理器（Finder/Explorer）的支持。

**第三方扩展 API (Plugin API)**：向社区开放标准接口。允许开发者为特定软件（如 Figma, Zotero, AutoCAD, VS Code）编写深度状态提取与恢复插件，实现无限的生态扩展。

**显式/隐式挂载**：支持用户手动将某个文件夹或链接"钉"在任务上，或由系统通过插件自动感应并保存。

###### **2. 逻辑层：八维状态机与单一独占协议 (State Machine & Single-Tasking)**

用严苛的逻辑流转消除认知损耗，对抗多任务焦虑。

**八维状态模型**：Draft (草稿) → Ready (就绪) → Scheduled (排期唤醒) → In Progress (执行中) → Paused (主动暂停) → Blocked (被动阻塞) → Done (完成) → Canceled (废弃)。

**In Progress 唯一排他原则**：系统物理级限制同时只能有一个任务处于执行状态。

**自动压栈机制 (Auto-Context Switch)**：当强制开启新任务时，后台自动将当前活跃任务转入 Paused，并瞬间调用插件完成现场快照封存。

###### **3. 交互层：沉浸式桌面 HUD 与柔性提醒 (Immersive Hover HUD)**

摒弃臃肿的主窗口，采用无感存在的"抬头显示器"。

**悬停交互 (Hover-to-Interact)**：HUD 半透明常驻屏幕边缘，默认鼠标穿透。仅当鼠标悬停达到设定时间阈值后，界面实体化并获取焦点，允许交互。

**时间压迫感视觉化**：根据任务 DDL（截止日期）的紧迫程度，HUD 的边框色温或呼吸频率会发生平滑变化。

**柔性心流熔断 (Flowtime Reminder)**：持续监测 In Progress 时长。超时后通过视觉动效提供温和的休息建议，但不强制锁定屏幕。

###### **4. 数据层：幽灵守护进程与 Git 持久化 (Ghost Daemon & Git Ledger)**

绝对的数据安全、轻量级的资源占用与无缝多端同步。

**无头运行 (Headless)**：核心调度器作为后台系统服务运行，接管倒计时、状态监听与自动化逻辑。

**Git 驱动的 Markdown 账本**：彻底抛弃关系型数据库。任务树、优先级、快照 Hash 等全部以规范化的 tasks.md 存储，由系统在后台静默执行 git commit。实现时光机级别的防灾回滚与私有云同步。

**全自动心流报表 (Zero-Click Reporting)**：系统自动记录任务起止时间及该时段内各软件的耗时占比，生成无需人工干预的复盘简报。

**被动上下文游标 (Passive Context Trail)**：在任务执行期，静默记录访问过的参考资料路径，形成任务专属的历史轨迹。

###### **5. 智能层：算法调度与 AI 辅助 (Smart Routing & BYOK)**

解决"万事开头难"与"不知道接下来干嘛"的决策疲劳。

**动态引力算法 (Gravity Score)**：本地引擎根据任务的优先级 (P0-P3)、距离 DDL 的剩余时间以及任务前置依赖，自动计算权重并置顶最迫切的任务。

**BYOK 自定义大模型接入**：允许填入自己的 AI API Key。

**智能任务降维**：面对复杂任务，呼出 AI 瞬间将其拆解为 15 分钟级别的本地 Markdown 微步骤。

下一跳建议：AI 结合当前语境和时间窗口，推荐最适合立刻动手的任务。

###### **6. 跨端层：社交软件全局网关 (Universal Messenger Gateway)**

用最轻的模式实现随时随地的灵感捕捉。

**对话即调度**：不开发独立的 iOS/Android App。通过接入 Telegram、微信机器人等现成网关，发送自然语言指令（如 /block 等待甲方审核 或发送一张参考图片），指令直达本地电脑后台同步状态与素材。

## 二、 未来战略构想 (Future Roadmap)

为产品建立坚固护城河的前沿技术储备（V2.0 及以后规划）。

###### MCP (Model Context Protocol) 协议打通：

构想：将我们的守护进程升级为标准的 MCP Server。

价值：让你电脑上的全局 AI（如 Claude Desktop 或 Cursor）能直接"看到"你的任务状态和物理桌面快照，实现真正的人机上下文交接。

###### 本地 RAG 记忆胶囊 (Task-Scoped Memory Capsule)：

构想：引入本地轻量级向量数据库（如 LanceDB）。

价值：不仅记录你看了什么网页，还会在后台静默将网页文本向量化压缩。未来恢复任务时，AI 可以直接基于你当时看过的资料回答问题，建立只属于该任务的"本地知识库"。

###### 无头浏览器主动轮询 (Active Condition Polling)：

构想：针对 Blocked 状态，引入 Puppeteer 等无头自动化脚本。

价值：从"被动等待超时提醒"升级为"主动去网页抓取审批状态"。状态一旦通过，系统自动将任务拉回 Ready 甚至直接弹出提醒"现场已备好，是否开工"。

**补充方案 1：纯命令行交互协议 (The CLI Command Set)**

既然没有了鼠标点击和悬停，我们需要一套符合人类直觉、借鉴 ctx（上下文切换）理念的终端命令集。我们将这个 CLI 工具命名为 flow。

**全局调度指令**：

flow ls：打印当前 Ready 状态的任务列表，按引力得分（Gravity Score）自动排序，终端高亮最推荐的任务。

flow status：在终端打印当前唯一处于 In Progress 的任务、已专注时长，以及是否达到了"建议休息"的阈值。

状态机引擎指令（核心驱动）：

flow add \"任务名称\" \--ddl \"明天\" \--p 1：向 tasks.md 写入新任务，状态默认为 Ready。

flow start \<TaskID\>：【核心魔法】系统在后台执行一系列动作：

寻找当前是否已有 In Progress 任务，若有则强制改为 Paused。

调用开源接口抓取当前桌面现场（写入本地 JSON/MD）。

将目标 TaskID 设为 In Progress。

执行 git commit -am \"Auto-switch to \<TaskID\>\"。

flow block \<TaskID\> \--reason \"等邮件\"：将任务打入冷宫，状态改为 Blocked。

flow done：完成当前高亮任务，归档并提交 Git。

**智能辅助指令**：

flow breakdown \<TaskID\>：触发 BYOK API，读取任务名，请求 AI 返回拆解步骤，并追加写入 tasks.md。

## 补充方案 2：开源生态的"白嫖"与桥接策略 (Open-Source Orchestration)

对于新手，这部分的原则是：绝对不写底层原生代码，全部通过 API 或子进程（Child Process）调用现成工具。

###### 1. 物理现场捕获 (接入 ActivityWatch)

避坑策略： 新手千万不要去研究 Windows 注册表或 macOS 的 Accessibility 权限来获取当前窗口。

实现路径： 让用户在电脑上安装开源的 ActivityWatch (AW) 客户端并保持后台运行。AW 默认会在本地开启一个 REST API (通常是 http://localhost:5600)。

你的代码逻辑： 当用户敲下 flow start 或 flow pause 时，你的 CLI 只需要发一个简单的 HTTP GET 请求给本地的 AW 接口，就能以 JSON 格式拿到"当前活跃的窗口名称"和"Chrome 正在浏览的 URL"。将这个 JSON 存入你的任务元数据中即可。极度简单！

###### 2. 纯文本账本与时光机 (桥接 Git)

避坑策略： 不要引入 SQLite 或 MongoDB 等数据库，配置环境会劝退新手。

实现路径： 选定一个本地文件夹（如 \~/.flow_engine/），所有的状态只在 tasks.md 文件里用正则表达式或 Markdown 解析库进行读写。

你的代码逻辑： 每次修改完 tasks.md，使用 Node.js 的 child_process.execSync 或 Python 的 subprocess，直接在后台静默运行 git add . 和 git commit -m \"Auto save\"。