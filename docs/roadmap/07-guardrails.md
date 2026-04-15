# 07. 执行护栏

这份文件只保留两类内容：

- 当前代码结构已经证明有价值的约束
- 历史文档里仍然可靠的经验

## 一. 通用护栏

### 1. 不要用概念词替代实现

下面这些词单独出现没有价值：

- 插件化
- 事件总线
- 服务层
- 状态机
- 解耦

只有落到这些具体产物上，才算真正成立：

- `Protocol`
- `dataclass`
- 明确 payload
- 明确 setup / teardown / cleanup
- 明确输入输出边界

### 2. 任何“对齐现有系统”的工作都先看代码

最低要求：

1. 锁定具体源码文件
2. 提取方法、数据结构、边界
3. 对照测试或规格
4. 再写路线或改实现

### 3. 把任务写成产出物，不写成口号

好的任务表达：

- 增加 `XxxPayload`
- 收口到 `TaskFlowRuntime`
- 为 `HudApp.register_widget()` 增加某种约束

差的任务表达：

- 完善插件化
- 重做架构
- 让系统更优雅

## 二. Runtime 护栏

### 1. 产品逻辑必须回到 canonical runtime / service path

不要把主逻辑塞回：

- CLI 表现层
- launcher
- adapter 临时分支
- widget 私有回调

### 2. 外部边界继续保持端口安全

不要向边界外泄漏：

- 内部 dataclass
- runtime 对象
- widget 实例
- raw protocol internals

### 3. 新能力不要绕开现有防御机制

继续使用：

- event bus
- hook manager
- breaker / failure isolation
- owner-aware cleanup
- runtime thread checks

## 三. HUD 护栏

这部分同时吸收当前 HUD runtime 结构和 `docs/past/hud-v1-postmortem.md` 的历史经验。

### 1. HUD 不允许重新长回大泥球

必须避免：

- UI 组件直接拥有状态流转
- IPC、动画、配置、输入监听混在一个模块
- 为了测一个小部件必须拉起整套桌面环境

### 2. HUD 升级必须基于现有 runtime

未来的交互、视觉、状态增强应继续挂在：

- `HudApp`
- transition runtime
- widget registration runtime
- task-status controller

而不是重新造一套 HUD 宿主。

### 3. 历史上已验证可行的技术，不必重复争论

来自历史复盘、仍可当经验使用的结论包括：

- Windows 透明 HUD 路径可行
- 鼠标监听与 UI 主线程隔离可行
- WSL / Windows TCP IPC 可行

这些是经验资源，不是当前产品已经完成的证明。

## 四. IPC 护栏

### 1. IPC 改动必须坚持 contract first

不要在业务代码里到处拼裸帧或复制 wire model。

### 2. 当前允许继续存在的债务边界必须收紧使用范围

当前可接受的是：

- `shared/flow_ipc` 继续作为边界层共享契约存在

当前不可接受的是：

- 在业务层扩散 `flow_ipc` 细节
- 前后端各自复制协议定义
- 在业务逻辑里直接做裸 JSON 拼帧

### 3. 完全协议独立工程只在触发条件成立时启动

例如：

- 第二个非 Python 消费端出现
- 发布节奏真的被共享运行时代码拖住
- 边界层 import 开始向业务层外溢

## 五. Launcher 护栏

这部分现在来自两类来源：

- `docs/past/windows-launcher-postmortem.md` 的历史经验
- 当前已核实的本地 launcher：
  - `C:\Users\27866\Desktop\flow-hud-control.cmd`
  - 同目录 `flow-hud-control.ps1`

因此更准确的理解是：

- launcher 不只是历史复盘对象
- 当前确实存在一条真实可用的本地启动链路
- 但它仍然不是通用分发方案

### 1. 脚本只做 orchestration

脚本可以负责：

- sync
- bootstrap
- start / stop / restart / status
- 环境探测、stamp 校验、配置生成

脚本不应负责：

- 任务语义
- HUD 产品逻辑
- widget 组合
- daemon 业务解释

当前这条本地 launcher 也基本遵守了这条边界：

- `.cmd` 只是薄包装
- `.ps1` 负责 orchestration
- 前端仍通过 `python -m flow_hud.windows_main` 启动
- 后端仍通过 `flow daemon start` 启动

### 2. 跨 shell 路径优先显式脚本文件

避免把复杂行为继续堆到长命令串里。

当前 launcher 也已经这样做：

- 通过生成 `backend-prepare.sh`、`backend-start.sh`、`backend-stop.sh` 等脚本交给 WSL 执行
- 而不是把所有逻辑都塞进嵌套命令串

### 3. launcher 变更必须走真实桌面入口验证

不要只靠静态 review 或 unit test 宣称“桌面路径没问题”。

当前已核实的 launcher 还说明了几条现实规则：

- 需要同时处理 Windows venv 与 WSL backend venv
- 需要保证 `hud_config.toml` 以 UTF-8 无 BOM 写出
- 需要保证 launcher 写入的 `HUD_DATA_DIR` 与前端 `HudConfig.load()` 的读取路径一致

## 六. AI 护栏

这部分是路线图约束，不是当前实现事实。

### 1. 先解决一个问题

第一目标应是：

- 把 `flow breakdown` 做成稳定能力

### 2. 失败必须可降级

AI 路径至少要守住：

- 超时
- 重试
- 错误分类
- 输出约束
- 不污染主任务流

### 3. 不要把 AI 变成第二套系统

AI 应增强任务流，不应绕开任务流。

## 七. 评审清单

以后任何中大型路线图变更，进入实现前至少过一遍这份清单：

- 有没有把产品逻辑塞回 launcher、CLI 表现层或 widget？
- 有没有绕过 `TaskFlowRuntime`、`HudApp` 或对应 service boundary？
- 有没有用抽象词代替具体契约？
- 有没有在业务层扩散 IPC 细节？
- 有没有把 HUD 再次推回高耦合结构？
- 有没有把历史经验误写成当前事实？
- 有没有把“当前本地可用 launcher”误写成“通用分发已完成”？
- AI 方案是不是仍然围绕一个明确问题？
- 有没有做最小但真实的验证？

## 八. 一句话护栏

**Flow 的后续演进必须坚持：产品逻辑回到 runtime，边界契约保持干净，历史经验不冒充现状，验证先于宣称。**
