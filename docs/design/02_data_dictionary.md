# Data Dictionary (MVP Version)

> 这是简化的MVP版本，专注于核心实体和字段。完整版参考：05_data_dictionary_full.md

---

## 1. raw_data

### Purpose
保存原始抓取数据，支持重新解析和调试。

### Fields
- `raw_id`: 唯一标识
- `source_type`: papers/blogs/advisories
- `url`: 原始链接
- `title`: 标题
- `fetched_at`: 抓取时间
- `published_at`: 发布时间（如果可获取）
- `content_path`: 原始内容文件路径
- `metadata`: 源特定的元数据（JSON）

### Storage
文件系统：`data/raw/{source_type}/{date}/{raw_id}.json`

---

## 2. artifact

### Purpose
统一的结构化内容对象，是评分、分类、报告的基础。

### Fields
- `artifact_id`: 唯一标识
- `source_type`: papers/blogs/advisories
- `url`: 原始链接
- `title`: 标题
- `authors`: 作者列表（如适用）
- `published_date`: 发布日期
- `fetched_date`: 抓取日期
- `raw_data_id`: 关联的raw_data ID
- `summary`: LLM生成的摘要
- `tags`: 标签列表
- `initial_score`: 初始评分
- `current_score`: 当前评分
- `score_breakdown`: 评分细分（JSON）
  - `recency_score`: 时效性得分
  - `authority_score`: 权威性得分
  - `relevance_score`: 相关度得分
- `status`: active/archived/rejected
- `created_at`: 创建时间
- `updated_at`: 最后更新时间

### Storage
文件系统：`data/artifacts/{date}/{artifact_id}.json`


---

## 3. theme

### Purpose
主题聚合，连接artifacts和candidate_directions。

### Fields
- `theme_id`: 唯一标识
- `name`: 主题名称
- `keywords`: 关键词列表
- `status`: core/candidate/archived
  - `core`: 用户确认的核心主题
  - `candidate`: 系统发现的待确认主题
  - `archived`: 已归档的主题
- `artifact_ids`: 关联的artifact ID列表
- `created_at`: 创建时间
- `confirmed_at`: 用户确认时间（如适用）

### Storage
文件系统：`data/themes/core_themes.json` 和 `data/themes/candidate_themes.json`

---

## 4. candidate_direction

### Purpose
候选研究方向，系统每周生成，用户审核和反馈。

### Fields
- `direction_id`: 唯一标识
- `name`: 方向名称
- `description`: 详细描述
- `thesis`: 核心论点
- `why_now`: 为什么现在是好时机
- `why_promising`: 为什么有前景（3-5年视角）
- `related_themes`: 关联的主题ID列表
- `supporting_artifacts`: 支撑材料的artifact ID列表
- `key_papers`: 关键论文列表


#### Multi-dimensional Scoring
- `novelty_score`: 新颖性 (1-5)
  - 是否提出新问题/新视角
- `impact_score`: 影响力潜力 (1-5)
  - 能支撑几篇四大论文
  - 对业界的潜在影响
- `feasibility_score`: 可行性 (1-5)
  - 技术可行性
  - 时间可行性（3-5年内）
- `industrial_value_score`: 工业价值 (1-5)
  - 是否解决业界实际痛点
  - 是否有明确应用场景
- `technical_contribution_score`: 技术贡献 (1-5)
  - 是否有新工具/新方法
  - 技术深度

#### User Feedback
- `pros`: 优点列表
- `cons`: 缺点列表
- `unknowns`: 未知问题列表
- `personal_notes`: 个人思考和笔记

#### Metadata
- `status`: active/under_review/archived
- `week_id`: 生成周次
- `created_at`: 创建时间
- `reviewed_at`: 用户审核时间

### Storage
文件系统：`data/directions/{direction_id}.json`


---

## 5. feedback_event

### Purpose
记录用户反馈，append-only，用于学习用户偏好。

### Fields
- `feedback_id`: 唯一标识
- `target_type`: artifact/theme/direction
- `target_id`: 目标对象ID
- `feedback_type`: like/dislike/pros/cons/note
- `content`: 反馈内容（JSON）
  - 对于artifact: {interested: true/false, note: "..."}
  - 对于direction: {pros: [...], cons: [...], notes: "..."}
- `timestamp`: 反馈时间

### Storage
文件系统：`data/feedback/{date}/feedback_events.json`

---

## 6. user_profile

### Purpose
用户的研究背景、价值观和偏好配置。

### Fields

#### Basic Info
- `current_research_area`: 当前研究领域
- `past_projects`: 已做项目主题列表
  - 不要求已发表，记录研究经验即可

#### Research Philosophy (价值观)
- `primary_goals`: 主要研究目标
  - 示例：["对工业界有实际影响", "产生学术认可的技术贡献"]


- `evaluation_criteria`: 评估研究方向的标准
  ```json
  {
    "industrial_impact": [
      "是否解决业界实际痛点",
      "是否有明确的应用场景",
      "业界顶级团队是否在关注",
      "是否能产生工业界可用的工具/方法"
    ],
    "academic_rigor": [
      "必须有技术贡献",
      "需要设计新的工具/方法/系统",
      "要有理论或实践上的创新"
    ]
  }
  ```

- `signal_sources_priority`: 信号源优先级
  - 示例：["业界安全团队博客", "高危漏洞", "顶会论文", "开源工具"]

#### Preferences (从反馈中学习)
- `preferred_topics`: 偏好的主题列表
- `avoided_topics`: 不感兴趣的主题列表
- `feedback_patterns`: 从历史反馈中提取的模式

#### Metadata
- `profile_version`: 版本号
- `last_updated`: 最后更新时间
- `last_manual_edit`: 最后手动编辑时间

### Storage
文件系统：
- `data/profile/config.json` (手动编辑)
- `data/profile/snapshots/{version}.json` (自动生成)


---

## 7. report

### Purpose
生成的日报和周报。

### Fields
- `report_id`: 唯一标识
- `report_type`: daily/weekly
- `period_key`: 时间标识（如"2026-W10"或"2026-03-08"）
- `content_path`: 报告内容文件路径
- `generated_at`: 生成时间

### Content Structure

#### Daily Report
- 新增高分artifacts列表
- 需要关注的新主题
- 快速浏览摘要

#### Weekly Report
- 本周统计和趋势
- 主题演化分析
- 新的candidate_directions（3个）
- 需要用户反馈的内容

### Storage
文件系统：`data/reports/{type}/{period_key}.md`

---

## 8. Data Relationships

```
raw_data
   ↓
artifact ──→ theme ──→ candidate_direction
   ↓           ↓              ↑
   ↓           ↓         research_gap
   ↓           ↓          ↗       ↖
   ↓     (学术轨聚类)  (空白检测交叉比对)
   ↓                         ↑
feedback ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
   ↓
user_profile (学习偏好)
   ↓
(影响后续artifact评分)
```

> **v2 新增实体 (2026-03-16)**:
> - `research_gap`：学术-工业空白检测结果。字段详见 `09_intelligence_layer.md` Section 3.4。
> - `candidate_direction` 新增 `gap_id`, `gap_score`, `barrier_score` 字段。
> - `user_profile` 新增 `domain_scope`, `direction_preferences` 字段。
> - 实际 ORM 模型以 `src/models/` 下的代码为准。

---

## 9. MVP Scope Summary

### 必须实现
- raw_data, artifact, theme, candidate_direction
- feedback_event, user_profile
- report

### 暂不实现
- artifact之间的关系图（artifact_edge）
- 复杂的版本控制和run_id
- 实时更新机制

### 可选扩展
- 阅读状态追踪
- 评分历史记录
- 主题演化可视化


---

## 10. Data Completeness Strategy

### 10.1 不同完整度的数据
由于会议论文的发布时间不同，系统需要处理不同完整度的数据：

- **title_only**: 仅有标题（最新会议，论文未正式发布）
- **with_authors**: 有标题和作者
- **with_abstract**: 有标题、作者、摘要
- **with_fulltext**: 有完整论文PDF

### 10.2 Artifact字段更新
在原有字段基础上增加：
- `data_completeness`: 数据完整度标记
- `abstract`: 摘要（可选）
- `pdf_url`: PDF链接（可选）

### 10.3 增量更新策略
- 初次爬取：获取可用的所有信息
- 定期更新：补充缺失的摘要和PDF
- 优先级：高分论文优先补充完整信息

