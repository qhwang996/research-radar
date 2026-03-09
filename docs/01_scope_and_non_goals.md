# Scope and Non-goals

## 1. In Scope for MVP

首版必须覆盖以下能力。

### 1.1 Source ingestion
支持至少 4 类输入：

- papers
- blogs
- advisories / vulnerability reports
- bookmarks

### 1.2 Raw preservation
所有输入需要先保存为 raw data，便于：

- 重新解析
- 规则变化后重算
- 调试和回溯

### 1.3 Artifact normalization
不同来源统一转换为 artifact，至少包含：

- title
- url
- published_at
- source_type
- source_tier
- summary
- external_ids
- tags

### 1.4 Deduplication
首版至少支持：

- canonical_id 硬去重
- external_id 半硬去重

### 1.5 Weekly shortlist generation
每周输出固定 3 个 candidate directions。

### 1.6 Markdown reporting
系统输出 markdown 格式的 daily / weekly / monthly reports。

### 1.7 Feedback recording
支持记录两类反馈：

- artifact 轻反馈
- direction 深反馈

### 1.8 Replay and comparison
改规则后允许重跑，并能比较结果变化。

---

## 2. Explicit Non-goals for MVP

首版明确不做以下内容。

### 2.1 Web UI
不开发网页前端，不做 dashboard。

### 2.2 Multi-user support
不做账号系统、权限系统、协作系统。

### 2.3 Distributed architecture
不做微服务、不做消息队列、不做分布式调度。

### 2.4 Full knowledge graph
不构建复杂知识图谱，也不做完整图数据库方案。

### 2.5 Heavy agent orchestration
首版不引入 LangGraph，不构建复杂 agent workflow。

### 2.6 Embedding-first clustering
首版不依赖复杂 embedding 聚类作为主逻辑。

### 2.7 Perfect topic generation
首版不追求“自动给出完美博士题目”，而是追求“给出值得继续思考的候选方向”。

---

## 3. Phase-2 Candidates

以下内容可以放到第二阶段：

- 更复杂的 theme builder
- 更丰富的 paper-specific metadata
- 更强的 explainability
- 更精细的 ranking
- 更完整的 source connectors
- 可视化比较视图
- 半自动方向演化跟踪

---

## 4. Phase-3 Candidates

以下内容可以更晚再做：

- 复杂调度系统
- 自动化监控
- 备份恢复自动化
- 复杂实体关系发现
- 更高级的 personalization engine

---

## 5. Scope Guardrails

开发中如出现功能膨胀，优先问以下问题：

1. 它是否直接帮助每周产生 3 个更好的候选方向？
2. 它是否直接支持 replay / compare / traceability？
3. 它是否首版就必须存在？

如果 3 个问题中多数答案是否，则推迟。