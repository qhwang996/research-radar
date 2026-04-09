# TRIAGE_POLICY

## 1. 目标

把所有进入系统的内容稳定分为 5 类：

1. `read_original`
2. `detailed_summary`
3. `one_line`
4. `delegate_to_agent`
5. `archive`

triage 的目标不是“更细的打分”，而是直接减少用户的管理成本。

## 2. 总体原则

- 先按 track 分流，再在 track 内 triage
- 先过滤已读和已归档
- 同一条内容在一个周期里只进入一个 bucket
- triage 是消费策略，不是永久标签
- 周期不同，阈值可以不同，但规则结构必须一致

## 3. bucket 定义

### 3.1 `read_original`
适用：
- 高价值
- 对当前研究最相关
- 原文不可替代
- 数量必须非常少

目标数量：
- daily: 0–3
- weekly: 3–10
- monthly: 5–15
- quarterly: 5–20（按主题归组）

### 3.2 `detailed_summary`
适用：
- 值得了解核心内容
- 但暂时不值得用户亲自读原文
- 应提供可独立阅读的详细摘要

目标数量：
- daily: 3–6
- weekly: 5–15
- monthly: 10–30

### 3.3 `one_line`
适用：
- 需要知道它出现了
- 不值得占用更多注意力
- 用 `summary_l1` 即可

### 3.4 `delegate_to_agent`
适用：
- 高价值但高摩擦
- 难读、长、抽象、门槛高
- 需要 agent 输出“读后可执行结论”

目标数量：
- daily: 0–3
- weekly: 1–8
- monthly: 3–12

### 3.5 `archive`
适用：
- 已读
- 重复
- 低价值
- 长期不相关
- 代读后确认无用
- 用户明确 dislike

## 4. academic track 规则

### 4.1 `read_original`
满足以下大部分条件时进入：
- `track == academic`
- unread
- 非 archive
- `source_tier == t1-conference` 且分数足够高
- 或 `source_tier == t2-arxiv` 但同时出现“新主题/高相关/gap 关联”
- 与当前 theme / gap / direction 强相关
- 不与本周期已选 paper 高度重复

### 4.2 `detailed_summary`
满足以下条件之一即可进入：
- 学术价值中高，但不值得立刻读原文
- 有结构化 `summary_l2`
- 可由 `summary_l3` 形成稳定详细摘要

### 4.3 `delegate_to_agent`
更偏向这些情况：
- T1 或高价值 T2
- 高 barrier topic
- 原文较长或摘要不足
- 方向上重要，但不适合用户立即投入
- 需要 agent 帮忙抽取方法、限制、open questions、可复用 idea

## 5. industry track 规则

### 5.1 `read_original`
满足以下大部分条件时进入：
- `track == industry`
- recent
- urgency 明显
- 出现多个独立来源重复信号
- 与当前研究主题强相关
- 不是单纯资讯噪音

### 5.2 `detailed_summary`
适合：
- 工业界真实痛点
- 值得了解脉络
- 但不值得读完原文
- 或可由 agent 先抽取“problem / affected systems / current workaround / unresolved gap”

### 5.3 `delegate_to_agent`
更偏向这些情况：
- 长博客 / 年度总结 / 深度复盘
- 有价值但阅读时间成本高
- 可能能映射到学术空白，但需要 agent 先做抽象

## 6. 跨轨道提升规则

如果条目满足以下任一条件，可以向上提一级 bucket：

- 被 `GapDetectionPipeline` 引用
- 被 `DirectionSynthesisPipeline` 引用
- 同时与 active theme 和 recent signal 关联
- 用户近期对相似条目持续 like / read

示例：
- 原本是 `detailed_summary` 的 academic paper，可提升为 `read_original`
- 原本是 `one_line` 的 industrial signal，可提升为 `delegate_to_agent`

## 7. 绝对禁止的混排

以下做法一律不允许：

- academic 与 industry 做一个总排行
- 用一套阈值解释所有内容
- 把 delegate 队列塞进 must-read 队列
- 把 candidate direction 当成普通 artifact 展示

## 8. 建议的最小实现方式

第一阶段不新增 triage 表，直接在 reporting 层做派生分类：

```python
def classify_for_period(artifact, track, period, read_ids, feedback):
    if artifact.id in read_ids:
        return "archive"
    if disliked_or_useless(artifact, feedback):
        return "archive"
    if should_delegate(artifact, track, period):
        return "delegate_to_agent"
    if should_read_original(artifact, track, period):
        return "read_original"
    if should_show_detailed(artifact, track, period):
        return "detailed_summary"
    return "one_line"
```

第二阶段才考虑把 triage hint 回写到 `score_breakdown`。

## 9. 反馈回流规则

### 用户动作 -> 回流信号
- 已读 -> 降低后续重复推荐概率
- like -> 提升相似主题或来源的优先级
- dislike -> 降低相似内容优先级
- delegate_useful -> 提高类似内容进入 delegate bucket 的概率
- delegate_useless -> 降低类似内容进入 delegate bucket 的概率

### 当前最小落地方案
- `read` 继续用现有 feedback event
- `like / dislike` 继续沿用现有 event
- `delegate_useful / delegate_useless` 第一阶段可存在 `content.subtype`
- monthly / quarterly 汇总这些 event，再做 profile / triage 调整

## 10. 与摘要字段的关系

- `summary_l1` -> `one_line`
- `summary_l2` -> machine-readable deep analysis（paper 优先）
- `summary_l3` -> detailed human-readable brief / delegate briefing

不要把 `summary_l2` 重定义为普通长摘要。
