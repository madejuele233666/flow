## 1. 编纂架构指引白皮书 (Documentation)

- [x] 1.1 将 `ai-arch-postmortem` 的 design.md 中的 5 种反模式分类学、7 项 Before/After 差距矩阵、根因链分析、对标法 SOP、20 项审计检查清单整合为一份独立的架构指引文件。
- [x] 1.2 在 `docs/` 下创建 `ai_architecture_guidelines.md`。按以下结构组织：
    - **第一章: AI 架构设计的 5 种失败模式** — 含衰减链 (Decay Chain) 模型图
    - **第二章: HUD V2 案例 — 7 项 Before/After 差距矩阵** — 从 design.md Decision 2 提取，每项附带对标的主引擎源码文件链接
    - **第三章: 根因链分析** — 从 design.md Decision 3 提取
    - **第四章: 对标法 (Alignment Protocol) SOP** — 从 design.md Decision 4 提取，含 5 步标准流程
    - **第五章: 架构审计检查清单** — 从 design.md Decision 5 提取，共 20 项可打勾检测点，分为 5 个维度（数据契约、边界隔离、防御机制、插件生态、任务清单防御）
    - **第六章: 正面经验沉淀** — 从 design.md Decision 6 提取
- [x] 1.3 在白皮书的第二章中，为每项差距提供具体的代码片段对比（Before 的空泛描述 vs After 的代码级定义）。代码引用应指向实际的主引擎源文件以便读者验证。

## 2. 编辑项目级全局准则 — `openspec/project.md` (Project-Level Guardrails)

- [x] 2.1 编辑 `openspec/project.md`（英文），写入高层方向性准则。
- [x] 2.2 控制 `project.md` 篇幅在 1 页以内。只包含方向性原则，不包含具体检查清单或 Before/After 案例。
- [x] 2.3 验证 `project.md` 生效：运行 `openspec instructions apply --change ai-arch-postmortem` 确认 CLI 正常运行（file 已存在于项目根上下文中）。

## 3. 编辑 Schema 工作流 — 注入 AI 自检环节 (Schema Workflow Self-Verification)

- [x] 3.1 在 `openspec/schemas/ai-postmortem-workflow/schema.yaml` 中，`design` artifact 的 `instruction` 字段已完整保留原有 `spec-driven` schema 的全部设计文档生成指令内容。
- [x] 3.2 在 `design` artifact 的 `instruction` 末尾追加了 AI 自检规则（对标法 SOP 触发 + 架构审计检查清单执行 + 覆盖报告附录）。
- [x] 3.3 在 `openspec/schemas/ai-postmortem-workflow/schema.yaml` 中，`tasks` artifact 的 `instruction` 字段已完整保留原有 `spec-driven` schema 的全部任务生成指令内容。
- [x] 3.4 在 `tasks` artifact 的 `instruction` 末尾追加了 AI 自检规则（检查点阻断 + 防腐规定 + 产出物锚点 + 任务等级标签）。
- [x] 3.5 更新 schema 的 `description` 字段为 "Spec-driven workflow with AI self-verification guardrails"，version 升至 2。
- [x] 3.6 验证 schema 完整性：`openspec schemas --json` 确认 schema 被正确识别，description 和 4 个 artifact 均正确。

## 4. 融入 AI 生成流水线 (AI Pipeline Integration)

- [x] 4.1 审查现有 `.agent/skills/` 下的架构相关 skill。确认没有适用于架构推演的 skill，新建 `openspec-architect` skill 。
- [x] 4.2 创建 `.agent/skills/openspec-architect/SKILL.md` ，7 步工作流嵌入：项目上下文加载、模式检测、对标法 SOP (5步)、审计检查清单 (16项)、设计产出规则、任务产出规则、验证阠闭。同时创建 `.agent/workflows/opsx-architect.md` 工作流文件。

## 5. 代码健康度扫描 (Codebase Health Scan)

- [x] 5.1 扫描 `flow_engine/` 中是否存在与白皮书规范相悖的技术傅：找到 `events.py:14` 中的 `emit(…, {"task_id": 1})——但确认为文档注释中的示例代码，非业务调用。实际业务调用（`daemon.py:275`）均使用了强类型 Payload。
- [x] 5.2 扫描结论：主引擎代码健康，无技术傅需要跟踪。

## 6. 验证与闭环 (Verification & Close)

- [x] 6.1 确认 `docs/ai_architecture_guidelines.md` 内容完整、可正常渲染：共 408 行，6 个章节全部完成。
- [x] 6.2 确认 `openspec/project.md` 的准则能够被 openspec CLI 正确读取：41 行，7 项准则全部包含。
- [x] 6.3 确认 `openspec/schemas/ai-postmortem-workflow/schema.yaml` 修改后 schema 被正确识别，description="Spec-driven workflow with AI self-verification guardrails"，4 个 artifact 均完整。
- [x] 6.4 确认 skill 文件语法正确且指令清晰：`openspec-architect/SKILL.md` 包含 6 个 MANDATORY/Guardrails/Alignment Protocol 关键实施点。
- [x] 6.5 模拟对抗测试通过：`openspec new change "test-guardrails" --schema ai-postmortem-workflow` 创建测试变更，`openspec instructions design` 输出中正确包含 "AI SELF-VERIFICATION (MANDATORY...)" 内容。测试完成后已清理测试变更。
- [x] 6.6 **【检查点】** 三层防御架构已完整落地：白皮书→ project.md → schema instruction → skill。请用户确认后将此变更标记为完成。
