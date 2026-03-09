# Architecture Overview

## 1. Design Goal

系统的架构目标不是支持复杂平台化能力，而是支持一个单人、长期、可重跑、可追溯的研究方向收敛流程。

核心链路：

`source -> raw_fetch -> artifact -> theme/theme_snapshot -> candidate_direction_snapshot -> report -> feedback_event -> profile_snapshot`

---

## 2. Technology Stack

### 2.1 Core Technologies

- **Language**: Python 3.10+
- **Database**: SQLite (MVP阶段)
- **ORM**: SQLAlchemy 2.0+
- **Task Scheduling**: APScheduler
- **LLM**: OpenAI API / Anthropic API
- **Web Scraping**: requests + BeautifulSoup4
- **Configuration**: python-dotenv + pydantic-settings
- **Testing**: pytest
- **Code Quality**: black (formatter) + ruff (linter)

### 2.2 Key Dependencies

```
sqlalchemy>=2.0.0
alembic>=1.12.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
apscheduler>=3.10.0
openai>=1.0.0
anthropic>=0.18.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
click>=8.1.0
pytest>=7.4.0
black>=23.0.0
ruff>=0.1.0
```

---

## 3. Directory Structure

```
research-radar/
├── src/
│   ├── models/          # 数据模型
│   ├── crawlers/        # 爬虫
│   ├── pipelines/       # 数据处理管道
│   ├── scoring/         # 评分引擎
│   ├── theme/           # 主题管理
│   ├── direction/       # 方向管理
│   ├── reporting/       # 报告生成
│   ├── feedback/        # 反馈管理
│   ├── evolution/       # 演化追踪(Phase 2)
│   ├── llm/             # LLM服务
│   ├── scheduler/       # 任务调度
│   └── cli/             # CLI工具
├── data/
│   ├── raw/
│   ├── processed/
│   ├── reports/
│   └── cache/
├── tests/
├── docs/
└── schemas/
```

详细目录结构见 15_implementation_guide.md

---

## 4. High-level Modules

### 2.1 Ingestion

#### Responsibility
- 从不同 source 拉取内容
- 保存原始输入
- 记录抓取元数据

#### Input
- source config
- source credentials / local feed
- manual import data

#### Output
- raw_fetch

#### Non-responsibility
- 不负责研究方向判断
- 不负责复杂摘要生成
- 不负责用户偏好建模

---

### 2.2 Normalization

#### Responsibility
- 解析 raw_fetch
- 抽取结构化字段
- 生成 canonical_id
- 执行基础去重
- 生成 artifact

#### Input
- raw_fetch
- normalize rules
- source-specific parsing rules

#### Output
- artifact
- optional artifact_edge

#### Non-responsibility
- 不负责最终 shortlist 排名
- 不负责最终报告生成

---

### 2.3 Theme / Candidate Building

#### Responsibility
- 对 artifact 做轻量聚合
- 构建 theme snapshot
- 组合 academic evidence 和 real-world signals
- 每周生成 3 个 candidate directions

#### Input
- artifacts
- scoring rules
- latest profile snapshot
- weekly time window

#### Output
- theme_snapshot
- candidate_direction_snapshot

#### Non-responsibility
- 不负责原始抓取
- 不负责持久反馈输入

---

### 2.4 Reporting

#### Responsibility
- 把结果组织成 markdown 报告
- 生成 daily / weekly / monthly reports
- 为每次报告生成 report_log

#### Input
- candidate_direction_snapshot
- theme_snapshot
- artifact summaries
- report templates

#### Output
- markdown files
- report_log

#### Non-responsibility
- 不负责方向打分
- 不负责更新 profile

---

### 2.5 Feedback & Profile

#### Responsibility
- 记录 artifact 级轻反馈
- 记录 direction 级深反馈
- 从 feedback_event 生成 profile_snapshot
- 为下一轮 ranking 提供 personal fit 信号

#### Input
- feedback event
- previous profile snapshot
- latest report references

#### Output
- feedback_event
- profile_snapshot

#### Non-responsibility
- 不直接负责 source ingestion
- 不直接修改历史输出对象

---

## 3. Persistence Strategy

### Must Persist
以下对象必须持久化：

- raw_fetch
- artifact
- theme_snapshot
- candidate_direction_snapshot
- feedback_event
- profile_snapshot
- report_log
- report_content

### Recomputable
以下对象允许重算：

- summary
- tags
- scores
- theme grouping
- weekly shortlist ranking
- profile derivation

---

## 4. Execution Model

首版采用分阶段 pipeline，而不是复杂图编排。

建议阶段如下：

1. ingest
2. normalize
3. dedup
4. build themes
5. build weekly candidates
6. generate reports
7. record feedback
8. update profile

每个阶段：

- 有明确输入输出
- 有明确唯一键
- 可以单独重跑
- 尽量减少隐式副作用

---

## 5. Storage Model

### Database
- SQLite for MVP
- SQLAlchemy ORM or Core

### File Storage
- local filesystem for raw content and report content

建议目录：

- `data/raw/`
- `data/reports/`
- `data/exports/`

---

## 6. Source Priority

### Tier 1
Academic papers

### Tier 2
Blogs / advisories / real-world signals

### Tier 3
Bookmarks / personal sources / custom feeds

排序和候选方向收敛时，Tier 1 权重大于 Tier 2，Tier 2 大于 Tier 3。

---

## 7. Architectural Principles

1. Pipeline first, framework second
2. Persist critical intermediates
3. Separate data processing from reporting
4. Separate feedback recording from profile derivation
5. Prefer snapshots over in-place mutation
6. Prefer explicit files and tables over hidden state

---

## 8. What can change later

后续最可能替换的模块：

- connector implementation
- scoring strategy
- theme builder
- profile derivation logic
- report templates
- model provider

因此这些模块都应尽量保持边界清晰。