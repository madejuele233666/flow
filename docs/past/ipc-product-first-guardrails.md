# IPC 过渡期产品优先守则

## 1. 目的

本文件定义一个明确的过渡期策略：

- 短期目标：先把产品做成可用。
- 中期目标：在不放大技术债的前提下继续迭代 IPC 能力。
- 长期目标：仍然是前后端只共享协议制品，不共享运行时代码。

这意味着当前可以暂缓 `ipc-spec-repo-extraction`，但不能无约束地继续堆积 IPC 相关实现。

## 2. 当前架构立场

当前仓库接受以下过渡态：

- `shared/flow_ipc` 作为 IPC V2 的共享契约运行时存在。
- backend 与 frontend 可以共同依赖该共享契约包。
- 产品功能可以继续建立在该过渡态之上。

当前仓库不接受以下状态：

- backend 与 frontend 各自重新复制 wire model、错误码、codec 或 hello schema。
- 业务模块绕过 IPC 边界直接拼接或解析裸协议帧。
- 把 `shared/flow_ipc` 当成通用业务模型层向外扩散。

## 3. 允许的技术债

当前明确接受且有边界的技术债只有一项：

| 债项 | 当前接受原因 | 控制手段 | 退出条件 |
|---|---|---|---|
| `shared/flow_ipc` 作为共享运行时契约 | 先收敛 V2 语义、降低迁移爆炸半径、优先交付产品 | 限制 import 面、禁止本地重复 wire 定义、所有协议变更仍走 contract-first | 启动 `ipc-spec-repo-extraction`，切换到 spec 制品 + 本地生成边界 |

除上表外，不接受新增“为了快，先这样”的 IPC 长期债务。

## 4. 强约束原则

### 4.1 Contract First

任何会影响互通的变更，先改协议契约，再改实现。至少需要同步更新：

- `docs/ipc-protocol-v2.md`
- `openspec/specs/ipc-protocol-v2-contract/spec.md`
- `openspec/specs/ipc-client/spec.md` 或 `openspec/specs/tcp-ipc-transport/spec.md`（如适用）

禁止先改某一端实现，再用“当前行为”倒逼协议文档补票。

### 4.2 Shared Runtime Only At Boundary

`flow_ipc` 只应停留在协议边界层，不能向业务层扩散。

允许直接依赖 `flow_ipc` 的产品代码范围：

- `backend/flow_engine/ipc/`
- `frontend/flow_hud/plugins/ipc/`

允许直接依赖 `flow_ipc` 的非产品代码范围：

- 与 IPC 契约直接相关的测试
- 守卫脚本或迁移工具

禁止的依赖方式：

- `backend/flow_engine` 其他业务模块直接 import `flow_ipc`
- `frontend/flow_hud` 非 IPC 插件模块直接 import `flow_ipc`
- 领域模型、服务层、UI 层把 `flow_ipc` 类型当作内部通用 DTO

### 4.3 No Duplicate Wire Definitions

新增或修改 IPC 帧结构时：

- 不得在 backend/frontend 本地新增独立 wire dataclass
- 不得复制 `request/response/push/hello/error` 结构定义
- 不得复制保留错误码表

如果需要新字段、新错误码或新控制消息，应先落到共享契约，再由边界层消费。

### 4.4 No Naked Frames In Business Code

业务代码不得直接：

- `json.dumps()` 拼协议帧
- `json.loads()` 解析协议帧
- 手写 `{"v":2,"type":...}` 之类的协议对象

协议编解码只能出现在边界模块内：

- backend: `flow_engine/ipc/*`
- frontend: `flow_hud/plugins/ipc/*`
- shared contract: `shared/flow_ipc/*`

### 4.5 Transport And Business Semantics Stay Separate

允许变更：

- transport 建链方式
- 端点解析方式
- 重连、超时、心跳等运行策略

但这些变更不得偷偷改变：

- 帧结构
- hello 语义
- 错误码语义
- `rpc` / `push` 角色语义

只要业务互通语义变了，就不是“实现细节”，必须回到协议契约。

### 4.6 Capability-Gated Evolution

新增可选行为时：

- 优先通过 capability 协商暴露
- 必须定义未协商时的降级路径
- 不允许依赖“双方当前都刚好支持”的隐式假设

### 4.7 Black-Box Verification Before Convenience

任何协议相关改动，至少补最小黑盒验证之一：

- codec/golden frame 测试
- hello/role/transport 矩阵测试
- 错误语义测试
- 前后端边界互通测试

不能因为当前还是单仓就只验证“内部函数能跑通”。

## 5. 产品开发时的操作规则

### 5.1 可以直接做的事

- 在现有 V2 契约上新增业务 method 或 push event
- 改进 backend/frontend 的 IPC 边界实现
- 增加产品功能，只要不突破本文件定义的 import 与协议边界
- 修复 `shared/flow_ipc` 中与现行 spec 不一致的问题

### 5.2 需要谨慎评审的事

- 修改 hello 字段
- 修改错误码语义
- 修改 endpoint resolution 默认值或优先级
- 在非边界模块中引入任何 `flow_ipc` 依赖

这类改动必须明确回答两个问题：

1. 这是产品功能所必需的吗？
2. 这会不会增加未来 `ipc-spec-repo-extraction` 的迁移成本？

如果第二个问题答案不清楚，默认先不做。

### 5.3 明确禁止的事

- 为了赶进度在 frontend/backend 各自复制一份协议模型
- 在业务层传递 `flow_ipc` 原始类型，导致边界失效
- 通过“共享默认值实现代码”替代“共享协议语义”
- 把实现层配置、部署默认值、环境变量解析规则继续混进协议主契约，扩大 future spec extraction 范围

## 6. 文档分层规则

为降低未来拆分成本，文档必须现在就分层：

- `docs/ipc-protocol-v2.md`：只保留会影响互通判定的协议事实
- 实现文档/部署文档：保留 endpoint discovery、环境变量、默认值、运行策略
- OpenSpec specs：保留必须执行和验证的约束

如果一段内容删掉后不会破坏跨端互通，它大概率不该继续留在协议主契约里。

## 7. 触发“恢复完全解耦”的条件

出现以下任一情况，就不应继续拖延 `ipc-spec-repo-extraction`：

- 前后端需要不同发布节奏，且共享运行时已开始造成升级阻塞
- 出现第二个非 Python 消费端或生成目标
- `flow_ipc` import 开始从边界层向业务层外溢
- 协议文档与共享契约出现反复手工同步成本
- 需要稳定的 conformance case 和跨版本 compat matrix 作为 release 门禁

## 8. Feature PR 自查清单

涉及 IPC 的产品改动合并前，至少自查：

- 是否修改了互通语义？如果是，协议文档和 specs 是否同步更新？
- 是否新增了 `flow_ipc` import？如果是，是否仍局限在边界层？
- 是否出现了本地重复 wire 定义？
- 是否有业务代码在拼接或解析裸帧？
- 是否补了最小相关验证？
- 是否让未来 spec extraction 更难了？如果是，为什么仍值得做？

## 9. 与长期路线的关系

本文件不是对完全解耦路线的否定，而是对其延期实施时的约束。

长期路线仍然保持不变：

1. 提取协议仓与机读制品
2. 前后端各自生成本地边界
3. 建立 conformance runner 与 compat-lab
4. 下线 `shared/flow_ipc` 运行时依赖

在那之前，本文件用于确保“先做产品”不会演变成“把过渡态固化成永久架构”。
