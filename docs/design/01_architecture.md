# Architecture & Data Flow

## 1. Design Goal

支持单人、长期、可重跑、可追溯的研究方向收敛流程。

核心链路（Phase 1-2，数据基座）：
```
Source → Raw JSON → Artifact → Score → Report → Feedback → Profile Update
```

Phase 3 扩展（智能分析层 v2：双轨 + 空白检测）：
```
                      Ingest (不变)
                 crawl → normalize → enrich(L1) → broad domain filter
                           |
             +-------------+-------------+
             |                           |
        ACADEMIC TRACK              INDUSTRY TRACK
        (T1 顶会 + T2 arXiv)       (T3 博客 + T4 未来快速源)
             |                           |
        L2 deep-analyze             signal-extract
             |                           |
        cluster → trend             demand signal 聚合
             |                           |
             +--- GAP DETECTOR ----------+
                       |
                DIRECTION SYNTHESIS → LANDSCAPE REPORT
```

完整设计见 `09_intelligence_layer.md`。

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
│   ├── pipelines/       # Normalization + Enrichment + Deep Analysis + Clustering + Trend + Direction Synthesis
│   ├── scoring/         # 评分引擎（Recency + Authority + Relevance）
│   ├── reporting/       # Daily / Landscape 报告生成
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

### 4.4 LLM Relevance (P7.2 → v4)
预计算 LLM 相关度分数：
1. 逐条调用 LLM (STANDARD tier)，评估**宽泛领域相关度**（v4：安全/SE 领域过滤，非具体关键词匹配）
2. 1-5 分映射为 0.0-1.0
3. v4 Profile 放宽后 `preferred_topics` 为空，relevance 完全由 LLM domain filter 决定

### 4.5 Score (P3.1)
**分轨评分**（v2 改造）：
- 学术轨（T1+T2）：`academic_score = domain_relevance×0.5 + recency×0.3 + authority×0.2`
- 工业轨（T3+T4）：`industry_score = recency×0.5 + domain_relevance×0.4 + authority×0.1`

### 4.6 Report (P4.1, P4.3)
- **Daily**: 博客推荐（近 3 天未读，最多 5 篇）+ 论文动态提示
- **Landscape**（替换原 Weekly）: 研究前沿地图 + 趋势洞察 + 候选方向 + 推荐阅读

### 4.7 Feedback (P5.1)
对 artifact / theme / direction 做 like/dislike/note/read，append-only。

### 4.8 Intelligence Layer (Phase 3 v2)

双轨处理 + 空白检测架构，详见 `09_intelligence_layer.md`：

**学术轨**（T1 顶会 + T2 arXiv）：
1. **Deep Analyze (L2)**: 对高相关论文生成结构化深度分析（已实现）
2. **Cluster**: 将论文按研究子领域聚类为 Theme（已实现）
3. **Trend Analyze**: 统计趋势 + 方法论演进

**工业轨**（T3 博客 + T4 未来快速源）：
4. **Signal Extract**: 从博客提取需求信号（问题/缺口/紧迫性）

**交叉比对**：
5. **Gap Detect**: 统计交叉比对学术覆盖 vs 工业需求，找出空白
6. **Synthesize Directions**: 基于空白 + Profile偏好，输出 2-3 个候选方向

---

## 5. Execution Model

分阶段 pipeline，CLI 驱动：

日常运行（daily）：
```
crawl → normalize → enrich → llm-relevance → score → daily-report
```

完整智能分析（weekly，`run --full`）：
```
crawl → normalize → enrich → llm-relevance(v4) → score(分轨)
  → deep-analyze (学术轨) + extract-signals (工业轨)
  → cluster → trend
  → detect-gaps (交叉比对)
  → synthesize → landscape-report
```

每个阶段有明确输入输出，可单独运行，可重跑。

---

## 6. Persistence Strategy

### Must Persist
- Raw JSON（原始数据）
- Artifact（结构化内容）
- Theme（研究子领域聚类快照）
- ResearchGap（学术-工业空白）
- CandidateDirection（候选研究方向）
- FeedbackEvent（用户反馈，append-only）
- Profile（用户画像，snapshot）
- Report（Markdown 文件）

### Recomputable
- summary_l1 / tags（LLM 输出，可带 cache 重算）
- summary_l2（论文 L2 深度分析 / 博客需求信号，可重算）
- scores（评分，可重算）
- Theme / ResearchGap / CandidateDirection（可重新生成，但 CORE Theme 需保留）

---

## 7. Architectural Principles

1. Pipeline first, framework second
2. Persist critical intermediates
3. Separate data processing from reporting
4. Prefer snapshots over in-place mutation
5. Prefer explicit files and tables over hidden state
