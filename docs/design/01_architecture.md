# Architecture & Data Flow

## 1. Design Goal

支持单人、长期、可重跑、可追溯的研究方向收敛流程。

核心链路：
```
Source → Raw JSON → Artifact → Score → Report → Feedback → Profile Update
```

Phase 1 简化：无 Theme / CandidateDirection，直接 Top 10 + 评分排序。

---

## 2. Technology Stack

- **Language**: Python 3.10+
- **Database**: SQLite (MVP)
- **ORM**: SQLAlchemy 2.0+
- **LLM**: OpenAI API / Anthropic API (raw HTTP, no SDK)
- **Web Scraping**: requests + BeautifulSoup4
- **CLI**: click
- **Testing**: pytest
- **Code Quality**: black + ruff

---

## 3. Directory Structure

```
research-radar/
├── src/
│   ├── models/          # SQLAlchemy ORM 模型
│   ├── repositories/    # Repository 层（CRUD 封装）
│   ├── crawlers/        # 爬虫（四大顶会 + 3 博客）
│   ├── pipelines/       # Normalization + Enrichment
│   ├── scoring/         # 评分引擎（Recency + Authority）
│   ├── reporting/       # Daily / Weekly 报告生成
│   ├── llm/             # LLM 客户端（provider + cache + retry）
│   ├── cli/             # CLI 入口
│   ├── db/              # 数据库 session 管理
│   └── exceptions.py    # 自定义异常
├── data/
│   ├── raw/             # 爬虫输出的 JSON
│   ├── reports/         # 生成的 Markdown 报告
│   └── cache/           # LLM 响应缓存
├── prompts/             # LLM prompt 模板
├── tests/
└── docs/
```

---

## 4. Pipeline Stages

### 4.1 Crawl
爬虫从配置的源抓取内容，保存为 JSON 到 `data/raw/`。

### 4.2 Normalize (P2.1)
纯数据转换，不调用 LLM：
1. 扫描未处理的 raw JSON（通过 RawFetch 记录追踪）
2. 提取元数据（作者、时间、来源等）
3. 生成 canonical_id（UUID5）
4. 去重（基于 canonical_id upsert）
5. 保存为 Artifact
6. 更新 RawFetch 处理状态

### 4.3 Enrich (P2.3)
调用 LLM 增强 artifact：
1. 读取未增强的 active artifact
2. 逐条调用 LLM (FAST tier) 生成 summary_l1 + tags
3. 写回 Artifact

### 4.4 Score (P3.1)
Phase 1 公式：`final_score = recency × 0.5 + authority × 0.5`

### 4.5 Report (P4.1)
- **Daily**: 按 created_at 过滤当日 artifact，score >= 0.6 展示
- **Weekly**: ISO week 窗口，Top 10 + 分数分布 + 按来源汇总

### 4.6 Feedback (P5.1)
Phase 1 只对 artifact 做 like/dislike/note，append-only，不影响评分。

---

## 5. Execution Model

分阶段 pipeline，CLI 驱动：
```
crawl → normalize → enrich → score → report
```

每个阶段有明确输入输出，可单独运行，可重跑。

---

## 6. Persistence Strategy

### Must Persist
- Raw JSON（原始数据）
- Artifact（结构化内容）
- FeedbackEvent（用户反馈，append-only）
- Profile（用户画像，snapshot）
- Report（Markdown 文件）

### Recomputable
- summary / tags（LLM 输出，可带 cache 重算）
- scores（评分，可重算）

---

## 7. Architectural Principles

1. Pipeline first, framework second
2. Persist critical intermediates
3. Separate data processing from reporting
4. Prefer snapshots over in-place mutation
5. Prefer explicit files and tables over hidden state
