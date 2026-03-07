## 1. 编纂架构指引白皮书 (Documentation)

- [ ] 1.1 将 `ai-arch-postmortem` 的 design.md 中的 5 种反模式分类学、7 项 Before/After 差距矩阵、根因链分析、对标法 SOP、20 项审计检查清单整合为一份独立的架构指引文件。
- [ ] 1.2 在 `docs/` 下创建 `ai_architecture_guidelines.md`。按以下结构组织：
    - **第一章: AI 架构设计的 5 种失败模式** — 含衰减链 (Decay Chain) 模型图
    - **第二章: HUD V2 案例 — 7 项 Before/After 差距矩阵** — 从 design.md Decision 2 提取，每项附带对标的主引擎源码文件链接
    - **第三章: 根因链分析** — 从 design.md Decision 3 提取
    - **第四章: 对标法 (Alignment Protocol) SOP** — 从 design.md Decision 4 提取，含 5 步标准流程
    - **第五章: 架构审计检查清单** — 从 design.md Decision 5 提取，共 20 项可打勾检测点，分为 5 个维度（数据契约、边界隔离、防御机制、插件生态、任务清单防御）
    - **第六章: 正面经验沉淀** — 从 design.md Decision 6 提取
- [ ] 1.3 在白皮书的第二章中，为每项差距提供具体的代码片段对比（Before 的空泛描述 vs After 的代码级定义）。代码引用应指向实际的主引擎源文件以便读者验证。

## 2. 融入 AI 生成流水线 (AI Pipeline Integration)

- [ ] 2.1 审查现有 `.agent/skills/` 下的架构相关 skill。确认是否有适用的 skill 可以扩展，或者需要新建 `openspec-architect` skill。
- [ ] 2.2 创建或扩展 skill 文件，在 SKILL.md 的指令中嵌入以下硬约束：
    - 当 AI 执行架构设计类任务时，必须自动加载 `docs/ai_architecture_guidelines.md` 中的检查清单
    - 在 `design.md` 产出完成后，AI 必须自行执行检查清单的逐项核对，并在文档末尾附上覆盖报告
    - 当用户指令包含"参考/对标/复刻"等关键词时，必须触发对标法 SOP 的 5 步流程
- [ ] 2.3 设计架构检查表嵌入机制：在 openspec 的 design.md 模板（如果有）或 skill 指令中，增加以下硬校验节点：
    - **设计产出前**: 列出所有对标源文件清单
    - **设计产出后**: 附上差距映射表（✅/❌/⚠️ 标注）
    - **tasks.md 产出后**: 确认每个高危步骤都有 `【检查点】` 阻断

## 3. 代码健康度扫描 (Codebase Health Scan)

- [ ] 3.1 扫描 `flow_engine/` 中是否存在与白皮书规范相悖的技术债：
    - 搜索未定义强类型载荷的事件发布点（`emit()` 调用处是否传入 `dict` 而非 dataclass）
    - 搜索是否有将领域对象直接暴露给外部消费者的泄漏点
    - 搜索是否有钩子调用绕过 HookManager 直接执行的情况
- [ ] 3.2 如果发现技术债，列出低优先级的修复清单（不在本变更中修复，但需归档跟踪）。

## 4. 验证与闭环 (Verification & Close)

- [ ] 4.1 确认 `docs/ai_architecture_guidelines.md` 内容完整、可正常渲染、所有代码引用指向正确的文件路径。
- [ ] 4.2 确认 skill 文件（新建或扩展的）语法正确且指令清晰。
- [ ] 4.3 做一次"模拟对抗测试"：用一个简单的虚拟场景（如"设计一个通知调度模块，参考 flow_engine 的 events 系统"），验证 AI 在加载了新 skill 后是否会自动执行对标法 SOP 和检查清单。
- [ ] 4.4 **【检查点】** 将白皮书终稿和 skill 配置展示给用户。确认教训已被完整吸纳后，标记此变更为完成。
