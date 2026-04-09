# TARGET_SYSTEM

## 1. 目标状态

目标不是推倒现有系统，而是在现有骨架上把仓库收敛成下面这条长期稳定链路：

```text
collect -> normalize -> enrich/filter -> score -> triage
        -> daily consumption
        -> weekly synthesis
        -> monthly consolidation
        -> quarterly strategy review
```

“研究方向发现”位于 triage 之后、周期总结之中，而不再直接压在 ingest 层之上。

## 2. 分层架构

### Layer A: Collection
负责“把东西拉进来”。
- crawlers
- raw json
- RawFetch / content_hash
- normalization / canonical_id

### Layer B: Understanding
负责“让内容变得可消费”。
- enrichment（L1 摘要 + tags）
- llm relevance / broad domain filter
- deep analysis（paper only）
- signal extraction（industry only）
- scoring

### Layer C: Triage
负责“决定用户怎么消费”。
- read original
- detailed summary
- one-line summary
- delegate to agent
- archive

### Layer D: Periodic Synthesis
负责“把短期情报沉淀成长期科研资产”。
- weekly
- monthly
- quarterly
- gap detection
- direction synthesis

## 3. 现有字段的目标语义

为了最小改动，优先复用现有字段，不做大 schema 改造。

### `Artifact.summary_l1`
保留当前含义：
- 一句话摘要
- 面向快速浏览
- 可直接用于日报的 one-line bucket

### `Artifact.summary_l2`
保留当前“结构化深度分析”语义：
- 优先给 academic papers 使用
- 存结构化 JSON 或可解析结构
- 不把它改成普通长摘要字段

### `Artifact.summary_l3`
作为新增的“详细消费层”承载位：
- human-readable detailed summary
- 或 delegate briefing seed
- 默认不要求所有 artifact 都填
- 优先只对进入 Detailed / Delegate bucket 的条目生成

### `Artifact.score_breakdown`
继续承载派生元信息，例如：
- `track`
- `weights`
- triage hints
- delegate recommendation
- summary generation version

第一阶段不要新增专门的 triage 数据表。

## 4. 报告层目标

### Daily
默认 5–10 分钟可读。
输出目标：
- 今日值得注意的条目
- 哪些要读原文
- 哪些只看一句话
- 哪些应交给 agent

### Weekly
默认 30–60 分钟可读。
输出目标：
- 本周 academic frontier
- 本周 industry signal
- 跨轨道 gap shortlist
- 下一周阅读队列

### Monthly
默认 60–90 分钟可读。
输出目标：
- 稳定主题
- 重复出现的 pain points
- feedback-based reading ROI
- 候选研究方向更新

### Quarterly
默认 1–2 小时可读。
输出目标：
- 真实值得进入研究路线图的方向
- source 保留/淘汰建议
- 反馈回流后的 profile 调整建议
- 过去一季的 reading / delegate / source performance 回顾

## 5. weekly 与 landscape 的收敛策略

当前代码里 `weekly` 与 `landscape` 同时存在。

目标策略是：

- `weekly` 成为面向用户的正式周报名称
- `landscape` 暂时保留为兼容别名或“weekly-strategic”输出
- 在未完成兼容迁移前，不删除 `landscape`
- 如果两个生成器同时存在，优先让它们共享策略，而不是各自漂移

## 6. 无法混排的规则

这些规则属于系统约束，不是报表风格偏好：

1. academic 与 industry 不进入同一个排序列表
2. paper relevance 与 industry urgency 不使用同一 bucket 解释
3. candidate direction 一定要注明证据来自哪个 track
4. advisories 接入后必须独立成 industry 子分区
5. delegate 队列与 must-read 队列不能混成一组

## 7. 高价值但难读条目的目标处理方式

条目进入 delegate bucket 的常见原因：
- 高 final_score / 高 track importance
- 摘要可读性差
- 原文长、抽象、门槛高
- 和当前 gap / direction 高相关
- 用户不值得立刻花原文阅读时间

delegate output 至少应包含：
- artifact id
- title
- source
- why delegated
- what to extract
- expected output shape
- linked theme / gap / direction（如果有）

## 8. 兼容优先原则

为了低维护，所有目标演进都遵守：

- 先加文档和兼容逻辑，再改默认行为
- 先加新的 report type，再决定是否废弃旧名字
- 先在 reporting 层实现 triage，再考虑持久化 triage
- 先用 feedback event 回流，再考虑复杂偏好模型
- 先让 source expansion 服从 triage/report，而不是反过来
