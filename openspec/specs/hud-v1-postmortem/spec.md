# hud-v1-postmortem Specification

## Purpose
TBD - created by archiving change hud-reset. Update Purpose after archive.
## Requirements
### Requirement: 经验教训文档
每次重大架构推倒重来时，MUST 产出一份结构化的 postmortem 文档，记录技术验证结论、失败原因和下一轮设计建议。

#### Scenario: 文档存在性
- **WHEN** HUD 代码被清除后检查 `docs/` 目录
- **THEN** 存在 `hud-v1-postmortem.md`，包含"技术验证结论"、"架构失败分析"和"下一轮设计建议"三个核心章节

#### Scenario: 知识可追溯
- **WHEN** 未来开发者开始第二轮 HUD 开发
- **THEN** 可以通过阅读 postmortem 文档，在 10 分钟内了解第一轮的全部关键发现和应避免的陷阱

