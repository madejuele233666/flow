# Layer 5：契约硬化

## 目标

只有在前面几层已经证明“稳定、值得、不会重新引入重机制”之后，
才把局部结构正式升级为 schema / shared contract。

## 为什么 Layer 5 必须后置

如果过早 schema 化：
- 会把临时设计冻结得过早
- 会把旁路能力重新灌进主路径
- 会让 rollout 变成“先写契约，再逼实现贴契约”

正确顺序应该是：

```text
先跑起来
  -> 再验证有价值
  -> 最后才 harden contract
```

## Layer 5 允许正式化的对象

只有以下对象在前层稳定后，才允许正式 schema 化：
- `review_scope`
- `review_coverage`
- `shared-findings-v2`
- tracked findings store
- variant analysis output

## 进入 Layer 5 的条件

必须全部满足：

1. Layer 1 已稳定
2. Layer 2 没有长成 gate
3. Layer 3 的白名单 family 没有明显噪声膨胀
4. Layer 4 没有显著拉高 closure latency
5. 团队已经验证 consumer 兼容性需求

## Layer 5 的实现方式

### 第一优先级

只对已经长期使用的结构补 schema。

例如：
- `shared-findings-v2.schema.json`
- `tracked-findings-v1.schema.json`
- `variant-analysis-v1.schema.json`

### 第二优先级

才考虑把 reviewer 内嵌结构抽成独立 artifact。

例如：
- 把 `review_scope` 从内嵌字段升级为独立 `review-plan.json`
- 把 `review_coverage` 从内嵌字段升级为独立 contract

## 明确反对的顺序

以下顺序是错误的：

```text
先单独建 planner schema
  -> 再逼 reviewer 去适配
```

正确顺序是：

```text
先让 reviewer 内嵌结构稳定
  -> 再抽成独立契约
```

## Layer 5 的止损点

出现以下任一情况，必须停止 schema 化：
- schema 数量增长快于真实收益
- consumer 兼容测试频繁失败
- 实现为了满足 schema 开始牺牲 review 质量
- 本应旁路的对象重新取得 authority 地位

## 验收标准

1. 新 schema 对应的是已经稳定存在的结构
2. schema 化没有新增主路径 gate
3. schema 化没有让 closure authority 扩张
4. consumer 兼容验证通过
