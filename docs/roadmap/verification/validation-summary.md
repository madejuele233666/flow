# Roadmap Verification Rerun Summary

状态基线：2026-04-15

这份记录用于说明 `docs-roadmap-refresh` 在 implementation working pass 出现阻塞 findings 之后，当前会话内做了哪些修复，以及同一个 verifier 会话的 working rerun 重新核对了什么。

## 修复内容

### 1. 修正 Context Recovery 现状表述

- `docs/roadmap/01-current-state.md`
  - 改为明确区分 capture 与 restore：
    - `pause` 以及 `start / resume` 中的 auto-pause 负责 capture
    - `start / resume` 负责 restore
- `docs/roadmap/03-workstreams.md`
  - 同步修正 Workstream B 的当前基线表述

对应代码锚点：

- `backend/flow_engine/task_flow_runtime.py`
- `backend/tests/test_task_flow_contract.py`

### 2. 补齐 Horizons C-F 的逐步验证段

- `docs/roadmap/13-horizon-c-hud-productization.md`
- `docs/roadmap/14-horizon-d-ai-assistance.md`
- `docs/roadmap/15-horizon-e-platform-and-delivery.md`
- `docs/roadmap/16-horizon-f-frontier-capabilities.md`

修复方式：

- 为缺失或不完整的步骤补上 `验证` 段
- 每步至少写清：
  - 现有锚点
  - 新增验证
  - 真实运行验证

### 3. 补齐 freshness audit 对归档源文档的覆盖

- `docs/roadmap/08-doc-freshness-audit.md`
  - 新增 `docs/past/aim.md` 分类：`stale`
  - 新增 `docs/past/unified-roadmap.md` 分类：`historical`
  - 补齐各自的原因、证据和处理建议

### 4. 修正根 README 的仓库布局表述

- `README.md`
  - 把仓库从“两个 workspace”改成“当前三个 active workspaces”
  - 明确 `shared/` 是共享 IPC 合约包工作区
  - 明确 `docs/`、`openspec/`、`.agent/` 仍是非 package 根目录资产

## Working Rerun 复核范围

本次 rerun 重新核对了以下几类内容：

- 修复后的 roadmap 文档：
  - `docs/roadmap/01-current-state.md`
  - `docs/roadmap/03-workstreams.md`
  - `docs/roadmap/08-doc-freshness-audit.md`
  - `docs/roadmap/13-horizon-c-hud-productization.md`
  - `docs/roadmap/14-horizon-d-ai-assistance.md`
  - `docs/roadmap/15-horizon-e-platform-and-delivery.md`
  - `docs/roadmap/16-horizon-f-frontier-capabilities.md`
- working pass 产物：
  - `docs/roadmap/verification/working-findings.json`
  - `docs/roadmap/verification/working-verifier-evidence.json`
- 代码与运行锚点：
  - `backend/flow_engine/task_flow_runtime.py`
  - `backend/tests/test_task_flow_contract.py`
  - `frontend/flow_hud/runtime.py`
  - `frontend/flow_hud/windows_main.py`
  - `frontend/flow_hud/core/app.py`
  - `frontend/flow_hud/task_status/controller.py`
  - `frontend/tests/hud/test_ipc_client_plugin.py`
  - `C:\\Users\\27866\\Desktop\\flow-hud-control.cmd`
  - `C:\\Users\\27866\\Desktop\\flow-hud-control.ps1`

## 修复后验证

- `git diff --check -- docs/roadmap README.md docs/past/README.md`
  - 已通过
- 文本自检
  - 已确认没有残留错误字样
- same-session verifier rerun
  - 原始 verifier 会话 `019d8eb1-cc45-7412-b9cb-cb5b0c211b88` 已在 working 语义下重新审查修复后的范围
  - 返回结果：`final_assessment=pass`，`findings=[]`
- challenger-derived working rerun
  - fresh challenger 会话 `019d8ecd-f8b1-7aa2-9381-1ad4e38fe3b7` 先发现 `README.md` 布局表述仍然过时
  - 修复 `README.md` 后，已把同一会话回收成 active working baseline 并 rerun
  - 返回结果：`final_assessment=pass`，`findings=[]`

## 当前结论

同一个 working verifier rerun 已确认先前 3 个 implementation findings 对应的问题都修到了 roadmap 文档内。

下一步只剩一件事：

- 再启动一个 fresh challenger verifier，确认是否还有新发现

## 最终 closure 结果

- 最终 fresh challenger 会话 `019d8ed4-5c2d-7f90-864c-e37d3c1b685b`
  - 返回结果：`final_assessment=pass`
  - `findings=[]`

结论：

- `docs-roadmap-refresh` 已完成：
  - 初始独立 working verifier
  - same-session working rerun
  - fresh challenger
  - challenger finding 转 active working baseline 后的 same-session rerun
  - 最终 fresh closure challenger
