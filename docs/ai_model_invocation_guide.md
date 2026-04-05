# 其他 AI 模型调用指南

本文档说明两件事：

1. 在这台机器和当前仓库里，如何直接调用不同厂商的 AI 模型。
2. 在 `Flow Engine` 项目内，如何把“其他模型”接到现有 BYOK 配置和后续 `flow breakdown` 能力上。

本文档刻意区分：

- `已验证可用`：我已经在当前环境里确认过的调用方式。
- `推荐接法`：结合当前代码结构，最适合接入本项目的方式。
- `尚未实现`：仓库里已有配置占位，但功能并未真正打通。

---

## 1. 当前仓库的真实状态

先把现状说清楚，避免把“将来设计”误写成“已经支持”。

### 1.1 已有配置占位

当前项目在 [flow_engine/config.py](/home/madejuele/projects/flow/flow_engine/config.py#L67) 定义了 `AIConfig`：

```python
@dataclass
class AIConfig:
    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    breakdown_max_steps: int = 8
```

这说明当前架构已经预留了一个“OpenAI 风格 / OpenAI-compatible”接入面：

- `api_key`
- `base_url`
- `model`

也就是说，从设计上看，本项目最容易先接的不是某一家专用 SDK，而是一个“统一 HTTP 适配层”。

### 1.2 CLI 已暴露入口，但还没真正接模型

`flow breakdown` 命令已经存在，见 [flow_engine/cli.py](/home/madejuele/projects/flow/flow_engine/cli.py#L301)。

但当前实际执行的拆解器仍是 stub，见 [flow_engine/scheduler/gravity.py](/home/madejuele/projects/flow/flow_engine/scheduler/gravity.py#L76)：

```python
class StubBreaker(TaskBreaker):
    def breakdown(self, task: Task) -> list[str]:
        return [f"[AI 未接入] 请手动拆解任务「{task.title}」"]
```

结论：

- 现在项目里有 AI 配置入口。
- 现在项目里有 AI 命令入口。
- 但“真正调用远程模型”的实现还没有接进去。

### 1.3 当前调用建议：优先直接调用，不再依赖外部命令

当前文档约定更新如下：

- 优先使用 HTTP API 或代码内 SDK 直接调用模型
- 不再把 `gemini`、`curl`、其他外部命令行工具视为默认接入方式
- CLI 仍可作为人工排障或手工 smoke test 的备选路径，但不应再作为主叙述

这意味着“如何调用其他模型”的默认答案已经变成：

- 在程序内直接发请求
- 通过统一 provider 抽象接入
- 把外部命令保留为非核心选项

---

## 2. “调用其他 AI 模型”到底有哪几种方式

从工程实现角度，调用方式可以分成四类。

### 2.1 程序内直接调用厂商 API / SDK

典型例子：

- OpenAI Responses API
- Anthropic Messages API
- Gemini `generateContent`
- 对应厂商的 Python / JS SDK

特点：

- 不依赖外部命令
- 最适合项目内正式接入
- 更容易做超时、重试、错误分类和日志
- 更符合后续 provider 抽象

适用场景：

- `Flow Engine` 这类项目内能力接入
- 正式功能开发
- 自动化、测试、服务端集成

### 2.2 厂商官方 CLI

典型例子：

- `gemini`
- 某些厂商提供的专用命令行工具

特点：

- 最适合手工验证
- 最适合快速 smoke test
- 对人类交互友好
- 不一定适合作为项目内长期依赖

适用场景：

- 先验证账号、网络、权限、模型名是否正确
- 先做最小可行调用
- 本地脚本串接

### 2.3 厂商原生 REST API

典型例子：

- OpenAI Responses API
- Anthropic Messages API
- Gemini `generateContent`

特点：

- 最稳定
- 功能最全
- 与厂商文档完全对齐
- 但不同厂商请求体格式不同，适配成本更高

适用场景：

- 要用该厂商专有能力
- 要长期稳定接入
- 要做正式产品化

### 2.4 OpenAI-compatible API

典型例子：

- OpenAI 官方兼容接口
- OpenRouter 的 OpenAI 兼容层
- 一些第三方网关
- 一些本地推理服务

特点：

- 同一套代码可切多个供应商
- 最适合当前项目现有 `AIConfig`
- 迁移成本最低

适用场景：

- `Flow Engine` 这类需要 BYOK 的项目
- 用户希望自由切换不同模型
- 先把能力打通，再逐步做厂商特化

### 2.5 本地模型服务

典型例子：

- `Ollama`
- 本地 `vLLM`
- 自建兼容网关

特点：

- 不依赖外网厂商
- 可控性高
- 通常延迟更高或效果更依赖本地硬件

适用场景：

- 强隐私
- 离线环境
- 内网部署

---

## 3. 推荐的接入优先级

对于这个仓库，推荐优先级如下：

1. 先统一走“程序内直接调用”的 `OpenAI-compatible HTTP adapter`
2. 如果需要厂商专有能力，再补原生 HTTP / SDK adapter
3. CLI adapter 只作为可选旁路，不再作为主路径

原因很直接：

- 当前 [flow_engine/config.py](/home/madejuele/projects/flow/flow_engine/config.py#L67) 已经天然偏向 `api_key + base_url + model`
- 这种配置最容易映射成程序内直接请求的兼容层
- 用户只要换 `base_url` 和 `model`，就能切模型
- 对 `flow breakdown` 这种文本生成类任务，兼容层通常已经足够

---

## 4. 各种调用方式的最小可行示例

这一章以“如何真正发出请求”为中心。

### 4.1 程序内直接调用：推荐默认路径

现在默认推荐的是“在代码里直接发请求”，而不是通过外部命令包一层。

Python 最小示例：

```python
import os
import requests

response = requests.post(
    "https://api.openai.com/v1/responses",
    headers={
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "model": "gpt-5",
        "input": "请将任务“重构 IPC 客户端”拆成 5 个 15 分钟步骤",
    },
    timeout=60,
)
response.raise_for_status()
print(response.json())
```

建议：

- 项目代码优先使用直接 HTTP / SDK 调用
- 在调用端统一设置超时、重试、错误分类
- 不要把外部命令执行包装成默认 provider

适合：

- 项目内正式接入
- 自动化调用
- 单元测试和集成测试

CLI 仍然可以保留，但只应作为备选调试路径。

### 4.2 OpenAI：原生 HTTP 调用

根据 OpenAI 官方文档，新项目优先使用 Responses API。

环境变量：

```bash
export OPENAI_API_KEY="your_api_key"
```

`curl` 示例：

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5",
    "input": "请将任务“重构 IPC 客户端”拆成 5 个 15 分钟步骤"
  }'
```

工程上要点：

- OpenAI 的新接口中心是 `responses`
- 如果只做文本生成，优先从 `input` 入手
- 返回体里通常要读取最终文本输出，而不是只看最外层字段

如果你要把它接入本项目，建议封装成：

```python
class OpenAIResponsesProvider:
    def generate(self, prompt: str) -> str: ...
```

### 4.3 Anthropic：原生 HTTP 调用

Anthropic 典型是 `messages` 接口。

环境变量：

```bash
export ANTHROPIC_API_KEY="your_api_key"
```

`curl` 示例：

```bash
curl https://api.anthropic.com/v1/messages \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{
    "model": "claude-sonnet-4-5",
    "max_tokens": 800,
    "messages": [
      {
        "role": "user",
        "content": "请将任务“实现 TCP IPC 客户端”拆解为 6 个具体步骤"
      }
    ]
  }'
```

工程上要点：

- Anthropic 请求体不是 OpenAI 风格
- 认证头不是 `Authorization: Bearer ...`
- 版本头通常是必需项

因此：

- Anthropic 最好单独做 `AnthropicMessagesProvider`
- 不要硬塞进 OpenAI 兼容结构，除非你经过了网关转译

### 4.4 Gemini：原生 HTTP 调用

Gemini 现在也应优先按“直接调用官方 API”来描述，而不是默认走 CLI。

环境变量：

```bash
export GEMINI_API_KEY="your_api_key"
```

`curl` 示例：

```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "contents": [
      {
        "parts": [
          { "text": "请把任务“补全文档”拆成 5 个步骤" }
        ]
      }
    ]
  }'
```

工程上要点：

- Gemini 原生 REST 结构与 OpenAI/Anthropic 都不同
- 如果只是人工调试，CLI 可以作为备选
- 如果要稳定嵌入应用服务，HTTP adapter 更合适

### 4.5 Ollama：本地模型调用

如果你不想依赖外部云服务，`Ollama` 是最常见的本地入口。

最小示例：

```bash
curl http://localhost:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5-coder:7b",
    "messages": [
      { "role": "user", "content": "请把任务拆成 4 步" }
    ],
    "stream": false
  }'
```

适合：

- 本地开发
- 无外网
- 隐私要求高

注意：

- 模型名取决于你本地实际拉取的模型
- 返回格式和云厂商不同，仍然需要 provider 适配

### 4.6 OpenAI-compatible 网关：最适合本项目

如果某个供应商或网关支持 OpenAI 兼容接口，那么你可以只改两样东西：

- `base_url`
- `model`

例如在这个项目里，最自然的配置形态就是：

```toml
[ai]
enabled = true
api_key = "your_api_key"
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
breakdown_max_steps = 8
```

如果改接别的兼容网关，本质上通常只需要：

```toml
[ai]
enabled = true
api_key = "your_api_key"
base_url = "https://your-provider.example/v1"
model = "your-model-name"
breakdown_max_steps = 8
```

在当前项目里，对应配置文件路径是：

- `~/.flow_engine/config.toml`

环境变量覆盖也已经存在，见 [flow_engine/config.py](/home/madejuele/projects/flow/flow_engine/config.py#L187)。

---

## 5. 在本项目里，应该如何设计“多模型调用”

如果要把“其他 AI 模型”真正接到 `Flow Engine`，不要在业务代码里到处写 `if provider == ...`。应该先定义统一协议。

### 5.1 推荐协议

```python
from typing import Protocol

class TextGenerationProvider(Protocol):
    def generate(self, prompt: str, *, system: str | None = None) -> str:
        ...
```

如果后面需要结构化输出，再升级成：

```python
class TextGenerationProvider(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        ...
```

### 5.2 推荐 provider 切分

建议至少切成这三类：

1. `OpenAICompatibleProvider`
2. `GeminiProvider`
3. `AnthropicMessagesProvider`

原因：

- `OpenAICompatibleProvider` 覆盖面最大
- `GeminiProvider` 更符合“直接调用优先”的新约定
- `AnthropicMessagesProvider` 结构独立，单独维护更清晰

### 5.3 推荐目录结构

建议新增目录：

```text
flow_engine/ai/
├── __init__.py
├── base.py
├── openai_compatible.py
├── gemini.py
├── anthropic.py
└── factory.py
```

职责建议：

- `base.py`: 协议和公共异常
- `openai_compatible.py`: 默认主实现
- `gemini.py`: Gemini 原生 HTTP / SDK
- `anthropic.py`: Anthropic 原生 HTTP
- `factory.py`: 根据配置创建 provider

### 5.4 工厂层示例

```python
class AIProviderError(RuntimeError):
    pass


def build_provider(config) -> TextGenerationProvider:
    provider = getattr(config.ai, "provider", "openai_compatible")

    if provider == "openai_compatible":
        return OpenAICompatibleProvider(
            api_key=config.ai.api_key,
            base_url=config.ai.base_url,
            model=config.ai.model,
        )
    if provider == "gemini":
        return GeminiProvider(
            api_key=config.ai.api_key,
            model=config.ai.model,
        )
    if provider == "anthropic":
        return AnthropicMessagesProvider(
            api_key=config.ai.api_key,
            model=config.ai.model,
        )
    raise AIProviderError(f"Unknown AI provider: {provider}")
```

这里有一个关键点：

当前 `AIConfig` 里还没有 `provider` 字段。

所以如果要正式支持多模型，第一步通常不是“直接写网络请求”，而是先把 `AIConfig` 扩成：

```python
provider: str = "openai_compatible"
timeout_seconds: float = 60.0
```

### 5.5 `flow breakdown` 的正确落点

当前 `flow breakdown` 的入口已经有了，不需要改命令形态。正确做法是替换 `StubBreaker`。

更准确地说，是新增一个真实实现，比如：

```python
class AITaskBreaker(TaskBreaker):
    def __init__(self, provider: TextGenerationProvider, max_steps: int) -> None:
        self._provider = provider
        self._max_steps = max_steps

    def breakdown(self, task: Task) -> list[str]:
        prompt = (
            f"请将任务《{task.title}》拆解为不超过 {self._max_steps} 个步骤。"
            "每一步必须具体、可执行、能在 15 分钟左右完成。"
            "只返回步骤列表，不要写解释。"
        )
        text = self._provider.generate(prompt)
        return parse_steps(text)
```

这样业务边界就是清晰的：

- `TaskBreaker` 只负责“任务拆解语义”
- `Provider` 只负责“向模型发请求”
- `parse_steps()` 只负责“把文本转成列表”

---

## 6. 鉴权、超时、重试、错误处理

这部分最容易被写漏，但实际接入时最关键。

### 6.1 鉴权策略

建议优先级：

1. 环境变量
2. `~/.flow_engine/config.toml`
3. 不要把 key 写死进仓库

对当前项目，已经存在这些环境变量覆盖入口：

- `FLOW_AI_API_KEY`
- `FLOW_AI_BASE_URL`
- `FLOW_AI_MODEL`

这些覆盖逻辑位于 [flow_engine/config.py](/home/madejuele/projects/flow/flow_engine/config.py#L187)。

### 6.2 超时

必须给每次调用设置超时。

原因：

- 网络问题会导致命令卡死
- 某些 CLI 在无输出时不代表失败，只是还没返回
- 任务管理系统不能被外部模型拖挂

建议：

- 直接 HTTP / SDK 调用：客户端超时默认 30 到 60 秒
- CLI 调用：如果保留，仅作为备选并在外层包 `timeout 30` 或 `timeout 60`

### 6.3 重试

只对“短暂性失败”重试。

可以重试的典型错误：

- 429
- 502
- 503
- 网络瞬断

不要重试的典型错误：

- 401 未授权
- 403 权限不足
- 404 模型名错误
- 400 请求体格式错误

建议退避：

- 第 1 次失败后等待 1 秒
- 第 2 次失败后等待 2 秒
- 第 3 次失败后等待 4 秒

### 6.4 错误分类

建议至少区分：

- `AuthenticationError`
- `RateLimitError`
- `TimeoutError`
- `ProviderResponseError`
- `ModelNotFoundError`

这样 CLI 输出才不会全是一个“AI 调用失败”。

---

## 7. 输出格式与解析策略

`flow breakdown` 这类功能最怕“模型很聪明，但输出不稳定”。

推荐策略有两种。

### 7.1 最稳妥：强约束纯文本列表

提示词直接要求：

```text
只输出 1 到 N 的编号列表。
每一项一行。
不要输出标题、说明、前言、结语。
```

然后本地解析：

- 去掉空行
- 提取 `1.` `2.` `3.` 开头的行
- 不足则回退为按换行切分

优点：

- 简单
- 不依赖某家特定 JSON 模式

缺点：

- 偶尔会遇到模型不守格式

### 7.2 更强：要求 JSON

让模型返回：

```json
{
  "steps": [
    "步骤一",
    "步骤二"
  ]
}
```

优点：

- 程序解析稳
- 后续更容易扩展成 `title/estimate/dependency`

缺点：

- 并非所有 provider 的“结构化输出支持”一致
- 不同厂商的 JSON 模式能力和参数名差异较大

对当前项目的建议：

- 第一版先做“纯文本编号列表”
- 第二版再做“JSON 严格模式”

---

## 8. 推荐落地方案

如果你的目标是“尽快让 `flow breakdown` 真正支持其他模型”，建议按以下顺序推进。

### 阶段 1：最低风险打通

1. 给 `AIConfig` 增加 `provider` 和 `timeout_seconds`
2. 新建 `TextGenerationProvider`
3. 先实现 `OpenAICompatibleProvider`
4. 用它替换 `StubBreaker`
5. 确保 `flow breakdown` 真正返回步骤列表

这样你就能立刻支持：

- OpenAI
- 任何兼容 OpenAI 的第三方网关
- 一部分本地兼容服务

### 阶段 2：补 Gemini 原生 provider

新增 `GeminiProvider`。

适用原因：

- Gemini 原生结构独立
- 可以避免把外部命令执行塞进核心调用链

但注意：

- Gemini 原生 provider 仍应纳入统一协议
- 不要让厂商特化逻辑泄漏到业务层

### 阶段 3：补厂商原生能力

仅当你确实需要时再加：

- `AnthropicMessagesProvider`
- `GeminiRestProvider`

典型触发条件：

- 你需要某家模型的专用参数
- 你需要某家模型的专用能力
- 兼容层已经不够表达

---

## 9. 常见坑

### 9.1 只改了 `model`，没改 `base_url`

很多人以为把 `model = "claude-..."` 填进去就能调用 Anthropic。

不对。

如果底层还是在调用 OpenAI 风格接口，那只改模型名通常是不够的。因为：

- 认证头可能不同
- 路径可能不同
- 请求体结构可能不同

### 9.2 把“CLI 能跑”当成“项目已接入”

CLI 能跑，只代表：

- 本机命令可执行
- 当前用户已鉴权
- 网络可达

不代表项目已经有：

- provider 抽象
- 结构化错误处理
- 可测试的集成点

### 9.3 没有设置超时

一旦不设超时，CLI 或 HTTP 都可能长时间挂住，尤其在：

- 无网
- 认证失效
- 沙箱限制

### 9.4 业务提示词和解析逻辑绑死在一起

正确方式是：

- prompt 模板独立
- provider 独立
- parser 独立

这样以后换模型时，代价最小。

---

## 10. 建议的配置模板

### 10.1 OpenAI-compatible

```toml
[ai]
enabled = true
provider = "openai_compatible"
api_key = "your_api_key"
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
breakdown_max_steps = 8
timeout_seconds = 60.0
```

### 10.2 Gemini 原生

```toml
[ai]
enabled = true
provider = "gemini"
api_key = "your_api_key"
model = "gemini-2.5-flash"
breakdown_max_steps = 8
timeout_seconds = 60.0
```

说明：

- 这种模式应直接调用 Gemini 官方 API
- 不再默认依赖本机安装的 `gemini` 命令

### 10.3 Anthropic 原生

```toml
[ai]
enabled = true
provider = "anthropic"
api_key = "your_api_key"
model = "claude-sonnet-4-5"
breakdown_max_steps = 8
timeout_seconds = 60.0
```

注意：

- 要实现这个配置，代码里必须有对应 provider
- 当前仓库还没有这个 provider

---

## 11. 一句话结论

如果只是“怎么调用其他 AI 模型”，答案是：

- 默认应在程序内直接调用模型，不再依赖外部命令
- 项目内最合理的统一接法仍然是 `OpenAI-compatible provider`
- `flow breakdown` 目前还没真正接模型，需要先替换 `StubBreaker`

如果你的目标是“最短路径把多模型接进 Flow Engine”，就按这个顺序做：

1. 扩 `AIConfig`
2. 加 `TextGenerationProvider`
3. 实现 `OpenAICompatibleProvider`
4. 接入 `AITaskBreaker`
5. 再补 `GeminiProvider`

---

## 12. 参考资料

以下是本次整理中用到的官方资料：

- OpenAI Text generation / Responses API: <https://platform.openai.com/docs/guides/chat-completions>
- Anthropic Messages API: <https://docs.anthropic.com/en/api/messages>
- Ollama API 文档: <https://docs.ollama.com/api>

这些链接用于说明调用形态；本仓库当前真实接线状态仍应以本地代码为准。
