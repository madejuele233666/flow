# IPC 独立开发解耦方案（前后端仅靠协议对齐）

## 1. 目标与边界

目标：前端与后端可在不同仓库、不同节奏下独立开发，只通过协议版本完成互通。

边界：
- 前后端不得依赖对方实现代码。
- 前后端可以依赖同一份协议制品（schema、错误码、状态机、示例帧、兼容规则）。
- 互通正确性由黑盒兼容测试保证，而不是联调默契。

## 2. 解耦原则

- Contract First：协议先于实现，变更先改协议再改代码。
- Single Source of Truth：协议事实只能有一个源（协议仓）。
- Tolerant Reader, Strict Writer：接收方容忍可选字段扩展，发送方严格遵守当前版本约束。
- Capability-gated Evolution：新增行为必须能力协商，不允许隐式行为漂移。
- Black-box Verification：验证输入输出帧，不验证内部函数。

## 3. 目标架构

### 3.1 三层拆分

1. 协议层（独立仓 `flow-ipc-spec`）
- `schemas/`：request/response/push/hello/error JSON Schema
- `rules/`：状态机、错误码语义、协商字段默认值与上下限
- `examples/`：规范示例帧与反例帧
- `conformance/`：黑盒测试向量（输入帧 -> 期望输出/行为）

2. 生成层（各端自生，不共享运行时）
- 前端：由 schema 生成本地类型、校验器、编解码边界代码。
- 后端：由 schema 生成本地类型、校验器、编解码边界代码。
- 两端生成结果各自提交到本仓，避免运行时交叉依赖。

3. 实现层（业务代码）
- 前端仅依赖本地生成的协议边界模块。
- 后端仅依赖本地生成的协议边界模块。
- 业务逻辑不得直接拼接裸 JSON 协议帧。

### 3.3 协议制品契约（必须机读）

为保证“只靠协议仓即可消费”，协议仓必须包含 `artifact-manifest.json`，最小结构如下：

```json
{
  "spec_version": "2.4.0",
  "schema_version": 1,
  "compat": {"min_client": "2.3.0", "min_server": "2.3.0"},
  "artifacts": {
    "schemas": "schemas/",
    "rules": "rules/",
    "examples": "examples/",
    "conformance": "conformance/"
  }
}
```

conformance 用例文件（`conformance/*.json`）最小字段：
- `id`：唯一 case id
- `protocol_version`
- `capabilities`：协商输入与期望能力
- `transport`：`unix|tcp`
- `timeline`：时序步骤数组（send/expect/sleep/close）
- `assertions`：期望帧、错误码、连接状态、超时窗口
- `timeouts_ms`：case 执行超时

统一 runner 接口（前后端都实现）：
- `conformance run --spec <tag-or-path> --sut <frontend|backend> --report <path>`
- 输出 `report.json`，至少含：`case_id`、`status`、`failure_step`、`expected`、`actual`

发布与 pin 规则：
- 发布介质：Git tag + 制品包（registry）二选一或并行
- 消费必须显式 pin（tag 或精确版本），禁止 floating latest
- CI 必须记录本次构建消费的协议版本号

### 3.2 当前仓库对应关系

- 协议文档主契约：[ipc-protocol-v2.md](/home/madejuele/projects/flow/docs/ipc-protocol-v2.md)
- 变更规范工件：
- [ipc-protocol-v2-contract/spec.md](/home/madejuele/projects/flow/openspec/changes/refactor-ipc-protocol-v2/specs/ipc-protocol-v2-contract/spec.md)
- [ipc-client/spec.md](/home/madejuele/projects/flow/openspec/changes/refactor-ipc-protocol-v2/specs/ipc-client/spec.md)
- 现有 shared 包可作为过渡期协议实现参考，但长期目标是“共享协议制品，不共享运行时代码”。
- 过渡规则：`ipc-protocol-v2.md` 中实现层参数（endpoint resolution、环境变量、部署默认值）在 Phase A 迁移到实现文档；协议主契约只保留会进入协商或影响互通判定的字段与语义。

## 4. 协议版本治理

### 4.1 SemVer 规则

- MAJOR：破坏兼容（删除字段、改变语义、改变强约束）。
- MINOR：向后兼容新增（可选字段、新 capability、新事件）。
- PATCH：文档修正、非行为修复、测试补强。

### 4.2 兼容声明（必须随版本发布）

每次发布协议版本时，必须附：
- 与上一版本兼容矩阵（client x server）。
- 新增 capability 列表及降级路径。
- 废弃项清单（含计划移除版本）。

### 4.3 协议冻结窗口

- 每个迭代设“协议冻结时间点”。
- 冻结后仅允许 PATCH，MINOR/MAJOR 进入下一迭代。

## 5. 变更流程（强约束）

1. 提案：先改协议仓（schema + 规则 + 示例 + conformance 向量）。
2. 审核：协议评审通过后打版本（如 `v2.4.0`）。
3. 消费：前后端分别升级到该协议版本并生成本地边界代码。
4. 验证：跑黑盒 conformance + 双端互通矩阵。
5. 发布：前后端各自按节奏发布，不要求同一天上线。

禁止：
- 先改某一端实现再“补协议”。
- 在业务代码中引入“对端实现细节假设”。

## 6. 测试策略（解耦核心）

### 6.1 协议一致性测试（单端）

每端必须通过：
- Schema 校验测试：所有入站/出站帧满足协议。
- 语义测试：错误码、重试标志、状态机转移符合规则。
- 向后兼容测试：新版本客户端/服务端与旧版本能力降级可运行。

### 6.2 黑盒互通测试（双端）

构建 `compat-lab`：
- 用容器或进程方式拉起 `frontend@X` 与 `backend@Y`。
- 执行协议向量集：hello、业务调用、push、异常帧、重连、降级。
- 输出矩阵：`(X,Y) -> pass/fail + 不兼容原因`。

建议矩阵最小集：
- `latest-client x latest-server`
- `latest-client x n-1-server`
- `n-1-client x latest-server`
- `lts-client x latest-server`（如有 LTS）

## 7. 能力协商与降级规范

- 新功能必须挂 capability（如 `push.timer.v2`）。
- 未协商能力时：
- 发送方不得发送该能力相关扩展行为。
- 接收方不得假设该能力存在。
- 需要显式拒绝时使用 `ERR_CAPABILITY_REQUIRED`，并返回 `error.data.required_capability`。

## 8. 配置与运行时解耦建议

### 8.1 配置分层

- 规范层（协议仓）定义：字段、语义、默认值、上下限、错误码、协商规则。
- 实现层（各端配置）定义：本地运行参数与策略值，但必须落在协议允许范围内。
- 必须协商的参数（例如 hello `limits` 相关）由协议字段承载并参与互通判定。
- 纯本地参数（例如日志采样率、内部线程轮询间隔）不进入协议协商。
- 环境变量只作为部署覆盖，不写入协议规范本体。

### 8.2 避免跨端耦合的实践

- 不共享“默认值实现代码”，只共享“默认值声明制品”。
- 不共享“业务 DTO”，只共享“协议 DTO schema”。
- 不共享“错误处理逻辑”，只共享“错误码契约与语义”。

## 9. 角色与责任

- Protocol Owner：维护协议仓，主持破坏性变更评审。
- Frontend Owner：保证前端协议边界实现与 conformance 通过。
- Backend Owner：保证后端协议边界实现与 conformance 通过。
- QA/Infra Owner：维护 compat-lab 与矩阵 CI。

审批规则：
- MAJOR 变更需三方同意（协议/前端/后端）。
- MINOR/PATCH 变更至少协议方 + 一端实现方同意。

## 10. 可观测性与回滚

- 统一日志字段：`protocol_version`、`capabilities`、`error.code`、`retryable`、`session_id`。
- 统一指标：
- hello 成功率
- capability 命中率
- 兼容失败率（按版本对）
- 重连次数与恢复时延

回滚策略：
- 客户端优先回滚到上一个兼容协议版本。
- 服务端保留 `n-1` 的能力兼容窗口。

## 11. 分阶段落地计划

### Phase A（1-2 周）：协议资产化

- 抽取协议仓结构（schema/rules/examples/conformance）。
- 从当前 V2 文档生成首版协议制品。
- 建立协议版本发布流程（tag + changelog + compatibility notes）。
- 将 `ipc-protocol-v2.md` 的实现层配置章节迁移到实现文档/部署指南。

验收：
- 协议仓可独立发布 `v2.x.y`，且附 `artifact-manifest.json`。
- `schemas/rules/conformance` 均可被 runner 解析（解析失败率 0）。
- 前后端各自 CI 能从同一 spec tag 拉取并生成边界代码。

### Phase B（1-2 周）：单端生成与边界收口

- 前后端接入各自生成工具链。
- 禁止业务代码直接拼裸帧（静态检查 + code review 规则）。
- 将协议入口统一收敛到边界模块。

验收：
- 编解码路径仅存在于边界模块。
- 关键协议类型来自生成结果（抽样检查 100% 通过）。
- 业务代码中裸帧拼接静态扫描为 0（新增 PR 不得引入）。

### Phase C（1-2 周）：compat-lab 与矩阵 CI

- 建立跨版本黑盒互通流水线。
- 设置发布门禁：矩阵未过不允许 release。

验收：
- 产出兼容矩阵报告，最少覆盖 `latest/latest`、`latest/n-1`、`n-1/latest`。
- 报告必须包含 `case_id`、`failure_step`、`expected`、`actual`。
- 发布门禁生效：矩阵存在失败时禁止合并 release 分支。

### Phase D（持续）：演进治理

- 新增功能全部 capability-gated。
- 维护 deprecation policy 与 LTS 兼容窗口。

验收：
- 每个新增协议能力都附 capability 名称与降级路径。
- 每个废弃项都有公告版本、移除版本、替代方案。
- LTS 兼容窗口有固定时长（例如 2 个 minor 周期）。

### Phase E（1-2 周）：shared 运行时迁移下线

- 双轨阶段：允许 shared runtime 与生成边界并存，但协议语义以 spec 制品为准。
- 切换阶段：前后端 import 从 `shared/flow_ipc` 迁移到各自生成边界模块。
- 守卫阶段：更新/替换 contract guard，禁止新增对 shared runtime 的协议定义依赖。
- 收敛阶段：确认 compat-lab 全绿后，移除 shared runtime 协议实现路径。

验收：
- 产品代码对 `shared/flow_ipc` 的协议 import 为 0（测试/迁移脚本目录除外）。
- 新 contract guard 生效：协议定义唯一来源为 spec 制品或生成边界，新增 shared 协议定义变更会被阻断。
- compat-lab 必测矩阵全绿（`latest/latest`、`latest/n-1`、`n-1/latest`）。
- shared runtime 协议实现路径已删除，或转入非运行态归档且不参与发布构建。

回滚策略：
- 任一阶段出现矩阵回归，允许回退到前一阶段并保留双轨。
- 回滚期间不得发布破坏兼容的协议版本。

## 12. 当前仓库建议的下一步

1. 在 `openspec` 新建 change：`ipc-spec-repo-extraction`。
2. 先落地 Phase A：把 [ipc-protocol-v2.md](/home/madejuele/projects/flow/docs/ipc-protocol-v2.md) 拆成可机读 schema + conformance 向量。
3. 在 CI 增加最小黑盒矩阵任务（latest vs latest，latest vs n-1）。
4. 完成后再推进生成链路替换，避免一次性大改风险。

如果当前阶段决定优先交付产品、暂缓 `ipc-spec-repo-extraction`，则必须遵守过渡期约束，避免把 shared runtime 过渡态固化为长期架构。见：[ipc-product-first-guardrails.md](/home/madejuele/projects/flow/docs/ipc-product-first-guardrails.md)。
