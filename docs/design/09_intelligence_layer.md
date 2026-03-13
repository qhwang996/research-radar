# Intelligence Layer - 研究情报分析

## 1. 设计背景

Research Radar Phase 1-2 建立了完整的数据基座：爬取→归一化→L1 增强→相关度评分→排序→报告。但这只覆盖了「感知前沿」，对用户最终目标「研究方向收敛」的贡献有限。

用户目标的四个层次：

| 层次 | 需要什么 | Phase 1-2 覆盖 |
|------|----------|---------------|
| 感知前沿 | 收集论文/博客/动态 | 已完成 |
| 整理结构 | 按主题/方法论聚类，看到领域全貌 | 未覆盖 |
| 分析逻辑 | 识别趋势、发现空白、理解演进关系 | 未覆盖 |
| 输出方向 | 基于分析提炼候选研究方向 | 未覆盖 |

本文档定义 Phase 3「智能分析层」的完整设计，在现有 pipeline 之上增加四条新 pipeline 和一种新报告类型。

---

## 2. 总体架构

### 2.1 Pipeline 拓展

现有 pipeline 保持不变，在 `score` 之后追加智能分析链：

```
[现有 — 保持不变]
crawl → normalize → enrich(L1) → llm-relevance → score
                                                    |
[新增 — 智能分析层]                                   v
                                        deep-analyze (L2, 逐条)
                                                    |
                                                    v
                                            cluster (批量)
                                                    |
                                                    v
                                        trend-analyze (逐 Theme)
                                                    |
                                                    v
                                      synthesize-directions (单次)
                                                    |
                                                    v
                                         landscape-report
```

### 2.2 数据流概览

```
~200 篇高相关论文  →  L2 深度分析（问题/方法/局限/开放问题）
                         ↓
                    ~10-15 个 Theme（研究子领域聚类）
                         ↓
                    每个 Theme 的趋势/方法演进/空白
                         ↓
                    2-3 个候选研究方向（含支撑论文和评分）
                         ↓
                    Landscape 全景报告（替换原周报）
```

---

## 3. 数据模型

### 3.1 Theme（研究子领域）

表名：`themes`，文件：`src/models/theme.py`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| theme_id | String(36), unique, indexed | UUID 业务主键 |
| name | String(200) | 主题名称，如「Web Fuzzing Techniques」 |
| description | Text | 2-3 句话描述这个子领域 |
| keywords | JSON (list[str]) | 代表性关键词 |
| artifact_ids | JSON (list[int]) | 关联论文的 artifact.id |
| artifact_count | Integer | 论文数量（冗余，便于查询） |
| paper_count_by_year | JSON (dict[str,int]) | 按年统计，如 `{"2022":5, "2023":12}` |
| methodology_tags | JSON (list[str]) | 常见研究方法 |
| open_questions | JSON (list[str]) | 从 L2 分析中提取的开放问题 |
| trend_direction | String(20) | `growing` / `stable` / `declining` |
| status | Enum(ThemeStatus) | `candidate` / `core` / `archived` |
| generation_version | String(50) | 如 `v1`，聚类版本，用于幂等 |
| week_id | String(10) | 如 `2026-W11`，生成时的 ISO 周 |
| created_at / updated_at | DateTime | 时间戳（继承 TimestampedModel） |

**ThemeStatus 枚举**（加入 `src/models/enums.py`）：

```python
class ThemeStatus(str, Enum):
    CANDIDATE = "candidate"   # 系统生成，待确认
    CORE = "core"             # 用户确认的核心主题
    ARCHIVED = "archived"     # 已归档或被合并
```

### 3.2 CandidateDirection（候选研究方向）

表名：`candidate_directions`，文件：`src/models/candidate_direction.py`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| direction_id | String(36), unique, indexed | UUID 业务主键 |
| title | String(300) | 方向标题 |
| description | Text | 3-5 句话描述 |
| rationale | Text | 为什么这个方向有价值 |
| why_now | Text | 为什么当前时机合适 |
| related_theme_ids | JSON (list[str]) | 关联的 theme_id 列表 |
| supporting_artifact_ids | JSON (list[int]) | 支撑论文的 artifact.id |
| key_papers | JSON (list[dict]) | `[{title, artifact_id, contribution}]` |
| open_questions | JSON (list[str]) | 这个方向待解决的问题 |
| novelty_score | Float, nullable | 新颖性（1-5 → 0.0-1.0） |
| impact_score | Float, nullable | 影响力（1-5 → 0.0-1.0） |
| feasibility_score | Float, nullable | 可行性（1-5 → 0.0-1.0） |
| composite_direction_score | Float, nullable | 加权综合分 |
| status | Enum(DirectionStatus) | `active` / `under_review` / `archived` |
| generation_version | String(50) | 版本号 |
| week_id | String(10) | 生成时的 ISO 周 |
| created_at / updated_at | DateTime | 时间戳 |

**DirectionStatus 枚举**（加入 `src/models/enums.py`）：

```python
class DirectionStatus(str, Enum):
    ACTIVE = "active"           # 当前推荐的方向
    UNDER_REVIEW = "under_review"  # 用户正在评估
    ARCHIVED = "archived"       # 不再推荐
```

### 3.3 现有模型变更

**不需要 schema 变更**。`Artifact.summary_l2`（Text, nullable）已存在，直接用于存储 L2 深度分析的 JSON 字符串。

### 3.4 新增 Repository

| Repository | 文件 | 关键方法 |
|------------|------|----------|
| `ThemeRepository` | `src/repositories/theme_repository.py` | `get_by_theme_id()`, `list_by_status()`, `list_by_week()`, `list_active_or_core()` |
| `CandidateDirectionRepository` | `src/repositories/candidate_direction_repository.py` | `get_by_direction_id()`, `list_by_week()`, `list_by_status()` |

遵循现有 `BaseRepository[T]` 泛型模式。

---

## 4. Pipeline 详细设计

### 4.1 DeepAnalysisPipeline（L2 深度分析）

**文件**：`src/pipelines/deep_analysis.py`

**目的**：对高相关论文生成结构化深度分析，填充 `Artifact.summary_l2`。

**筛选条件**：
- `relevance_score >= 0.6`
- `summary_l2 IS NULL`（未分析过）
- `source_type == PAPERS`

**输出格式**（JSON 字符串存入 `summary_l2`）：

```json
{
  "research_problem": "这篇论文要解决什么问题",
  "motivation": "为什么这个问题重要/现有方案的不足",
  "methodology": "核心方法/技术路线",
  "core_contributions": ["贡献1", "贡献2"],
  "limitations": ["局限1", "局限2"],
  "open_questions": ["可进一步研究的问题1", "问题2"],
  "related_concepts": ["相关概念/技术1", "技术2"]
}
```

**配置**：
- LLM Tier: STANDARD
- max_tokens: 1500
- temperature: 0.3
- cache_key: `deep_analysis_{analysis_version}_{canonical_id}`
- max_workers: 4（STANDARD 调用较慢，控制并发）
- prompt 模板：`prompts/deep_analysis.md`（中文）

**幂等性**：
- 已有 `summary_l2` 的 artifact 自动跳过
- `analysis_version` 版本变更时，支持 `--force` 清空并重新分析

**架构模式**：完全复用 `EnrichmentPipeline` 的设计模式（ThreadPoolExecutor + thread-local LLMClient + ProfileContext snapshot + JSON 解析容错）。

### 4.2 ClusteringPipeline（主题聚类）

**文件**：`src/pipelines/clustering.py`

**目的**：将高相关论文按研究子领域聚类，生成 Theme 记录。

**设计决策：LLM 聚类 vs Embedding 聚类**

选择 LLM-based 聚类，原因：
1. 语料规模小（~200 篇），LLM 上下文足够
2. LLM 能理解「研究问题相似性」，而非表面词汇相似性
3. 避免引入 sentence-transformers 等新依赖
4. 与现有 LLM 基础设施（provider + cache + retry）一致

**算法**：

1. **收集**：筛选 `relevance_score >= 0.6 AND summary_l2 IS NOT NULL` 的论文
2. **压缩表示**：每篇论文提取 `{id, title, research_problem, methodology, core_contributions}`（从 L2 JSON）
3. **分批聚类**：每批 30-40 篇，发送到 LLM，要求返回聚类标签和论文分配
4. **合并去重**：一次 merge 调用，将各批次的聚类标签合并（语义相似的合为一个）
5. **持久化**：写入 Theme 记录

**LLM 配置**：
- 分批调用：STANDARD tier
- Merge 调用：PREMIUM tier（需要全局视角）
- prompt 模板：`prompts/cluster_papers.md`（中文）
- cache_key: `cluster_{cluster_version}_{sha256(sorted_canonical_ids)}`

**增量策略**：
- 首次运行：全量聚类
- 后续运行：
  - 新论文先尝试分类到已有 Theme（单独 LLM 调用）
  - 累积 >10 篇无法分类的论文时，触发全量重聚类
  - `status == CORE` 的 Theme 在重聚类时作为锚点保留

### 4.3 TrendAnalysisPipeline（趋势分析）

**文件**：`src/pipelines/trend_analysis.py`

**目的**：为每个 Theme 计算趋势指标，包括定量统计和定性分析。

**处理逻辑**：

1. **定量分析**（纯计算，无 LLM）：
   - 按年统计论文数 → `paper_count_by_year`
   - 判断 `trend_direction`：近 2 年论文数 > 前 2 年 → `growing`，反之 → `declining`，持平 → `stable`

2. **定性分析**（LLM）：
   - 输入：该 Theme 下所有论文的 L2 分析（research_problem + methodology + limitations）
   - 输出：方法论演进总结、高频 limitation/open_question 归纳
   - 更新 Theme 的 `methodology_tags` 和 `open_questions`

**LLM 配置**：
- Tier: STANDARD
- prompt 模板：`prompts/analyze_theme_trend.md`（中文）
- cache_key: `trend_{trend_version}_{theme_id}_{sha256(artifact_l2s)}`

### 4.4 DirectionSynthesisPipeline（方向综合）

**文件**：`src/pipelines/direction_synthesis.py`

**目的**：综合 Theme 全景、趋势分析和用户画像，输出 2-3 个候选研究方向。

**输入**：
- 所有 `status IN (candidate, core)` 的 Theme（含 trend_direction, open_questions）
- 最新 active Profile（含 current_research_area, interests, past_projects, primary_goals, evaluation_criteria）
- 用户在 Theme 和 Direction 上的历史反馈（`FeedbackTargetType.THEME/DIRECTION`）

**输出**：
- 2-3 个 `CandidateDirection` 记录，每个包含：
  - title, description, rationale, why_now
  - 三维评分（novelty, impact, feasibility）
  - 支撑论文列表（key_papers）
  - 关联 Theme（related_theme_ids）
  - 待解决问题（open_questions）

**LLM 配置**：
- Tier: **PREMIUM**（这是系统的核心输出，质量优先）
- max_tokens: 4000
- temperature: 0.5（允许一定创造性）
- prompt 模板：`prompts/build_candidate_direction.md`（利用现有空文件）
- cache_key: `direction_{direction_version}_{week_id}_{sha256(themes+profile)}`

**幂等性**：按 `week_id + generation_version` 判断是否已生成。

---

## 5. Landscape 全景报告

### 5.1 定位

**替换现有周报**。用户每周 1-2 小时时间，Landscape 报告同时覆盖「论文推荐」和「方向分析」功能。

日报保持不变（博客推荐）。

### 5.2 文件

- 生成器：`src/reporting/landscape.py`（继承 `BaseReportGenerator`）
- 输出路径：`data/reports/weekly/YYYY-WXX.md`（复用周报目录）

### 5.3 报告结构

```markdown
# Research Radar - 研究前沿全景报告
**周**: YYYY-WXX
**周期**: YYYY-MM-DD 至 YYYY-MM-DD
**生成时间**: YYYY-MM-DD HH:MM

---

## 研究前沿地图

当前追踪 N 个研究子领域，涵盖 M 篇高相关论文。

### 1. [Theme Name] ▲ 上升趋势
- **论文数**: 2022: X | 2023: Y | 2024: Z | 2025: W
- **代表方法**: method1, method2, method3
- **关键开放问题**:
  - 问题1...
  - 问题2...
- **代表论文**: [Paper A] (USENIX 2025), [Paper B] (CCS 2024)

### 2. [Theme Name] — 稳定
...

---

## 趋势洞察

### 上升领域
- [Theme]: 近两年论文数增长 X%，关键驱动...

### 方法论演进
- 从 X 方法向 Y 方法转变的趋势...

### 研究空白
- **空白 1**: 多篇论文提到但未解决...
- **空白 2**: ...

---

## 候选研究方向

### 方向 1: [Direction Title]
- **概述**: ...
- **为什么现在**: ...
- **新颖性**: ★★★★☆  |  **影响力**: ★★★★★  |  **可行性**: ★★★☆☆
- **支撑论文**:
  - [Paper A] (USENIX 2025) — 贡献...
  - [Paper B] (CCS 2024) — 贡献...
- **待解决问题**:
  - 问题1...
  - 问题2...
- **建议下一步**: ...

### 方向 2: [Direction Title]
...

---

## 推荐阅读

支撑以上方向的论文，按优先级排序（排除已读）。

| # | 标题 | 来源 | 关联方向 | 相关度 | 状态 |
|---|------|------|----------|--------|------|
| 1 | ... | USENIX 2025 | 方向1 | 0.95 | 未读 |
| 2 | ... | CCS 2024 | 方向1,2 | 0.88 | 未读 |

---

## 本周博客回顾

| # | 标题 | 来源 | 相关度 | 状态 |
|---|------|------|--------|------|
| 1 | ... | PortSwigger | 0.85 | 未读 |

---

## 统计
- 高相关论文总数: X（已深度分析: Y）
- 研究子领域数: Z
- 累计候选方向数: W
- 数据库总量: T
```

---

## 6. CLI 集成

### 6.1 新增命令

| 命令 | 说明 | 关键参数 |
|------|------|----------|
| `deep-analyze` | L2 深度分析 | `--provider`, `--artifact-id`, `--workers 4`, `--min-relevance 0.6` |
| `cluster` | 主题聚类 | `--provider`, `--full/--incremental`, `--min-relevance 0.6` |
| `trend` | 趋势分析 | `--provider`, `--theme-id` |
| `synthesize` | 方向综合 | `--provider`, `--week-id` |

### 6.2 报告命令扩展

```bash
research-radar report --type landscape [--date YYYY-MM-DD]
```

`landscape` 替换 `weekly`，代码中 `weekly` 保留但标注 deprecated。

### 6.3 反馈命令扩展

现有 `feedback` 命令增加互斥目标选项：

```bash
# 现有
research-radar feedback --artifact-id 123 --type read

# 新增
research-radar feedback --theme-id UUID --type like
research-radar feedback --direction-id UUID --type like --note "very promising"
```

`--artifact-id`、`--theme-id`、`--direction-id` 三选一（互斥组）。

### 6.4 `run` 命令扩展

新增 `--full` 标志：

```bash
# 默认（日常运行，不变）
research-radar run --provider openai --report-type daily

# 完整智能分析链（通常每周运行一次）
research-radar run --full --provider openai
```

`--full` 在现有 pipeline 之后追加：
`deep-analyze → cluster → trend → synthesize → landscape-report`

---

## 7. Prompt 模板

### 7.1 新建模板

| 文件 | 用途 | 语言 |
|------|------|------|
| `prompts/deep_analysis.md` | L2 深度分析 | 中文 |
| `prompts/cluster_papers.md` | 批量聚类 | 中文 |
| `prompts/analyze_theme_trend.md` | 趋势分析 | 中文 |

### 7.2 填充现有空模板

| 文件 | 用途 | 语言 |
|------|------|------|
| `prompts/build_candidate_direction.md` | 方向综合 | 中文 |
| `prompts/extract_profile_signals.md` | 反馈信号提取 | 中文 |

---

## 8. LLM 成本估算

| 阶段 | Tier | 每次 token | 调用次数 | 频率 | 估算成本 |
|------|------|-----------|---------|------|---------|
| L2 深度分析 | STANDARD | ~2000 in / ~800 out | ~200（首次），~5-10/周 | 增量 | 首次 $4-6，后续 $0.1-0.3/周 |
| 聚类（分批） | STANDARD | ~4000 in / ~1000 out | 5-7 批 | 全量时 | $1-2/次 |
| 聚类（merge） | PREMIUM | ~3000 in / ~1500 out | 1 次 | 全量时 | $0.5-1/次 |
| 趋势分析 | STANDARD | ~3000 in / ~800 out | 10-15 Theme | 每周 | $0.5-1/周 |
| 方向综合 | PREMIUM | ~5000 in / ~2000 out | 1 次 | 每周 | $0.5-1/周 |

**首次运行总成本**：约 $8-12（一次性 L2 分析 + 首次聚类）
**每周运行成本**：约 $2-4（增量分析 + 趋势 + 方向综合）

全部结果通过 `FileLLMCache` 缓存，重跑不产生额外成本。

---

## 9. 设计决策

### D13: LLM 聚类 > Embedding 聚类

**决策**：使用 LLM 直接聚类，不引入 embedding 基础设施。

**理由**：
- 语料小（~200 篇），不需要向量检索的效率优势
- LLM 能理解「研究问题相似性」而非表面词汇相似性
- 避免新增 sentence-transformers 依赖
- 与现有 LLM 基础设施一致

**权衡**：每次全量聚类成本更高（$2-3 vs embedding 方案的 $0.1），但运行频率低（每周或触发式）。

### D14: L2 分析存 JSON 在 summary_l2 字段

**决策**：L2 结构化分析存为 JSON 字符串在现有 `Artifact.summary_l2` Text 字段中。

**理由**：
- 不需要 schema 迁移，`summary_l2` 已存在
- L2 数据作为整体产生和消费
- 新增 7+ 个字段会臃肿 Artifact 模型
- JSON 在下游解析足够简单

### D15: Theme 为快照，非实时聚合

**决策**：Theme 存储 `artifact_ids` 快照和 `week_id`，而非动态聚合查询。

**理由**：
- 遵循架构原则「prefer snapshots over in-place mutation」
- 支持跨周对比（Theme 在不同周的论文数变化）
- 用户确认的 `CORE` Theme 需要持久化，不被重聚类覆盖

### D16: Landscape 报告替换周报

**决策**：Landscape 全景报告替换现有 `WeeklyReportGenerator`，不并存。

**理由**：
- 用户每周只有 1-2 小时，同时看两份报告信息过载
- Landscape 报告已包含论文推荐功能（推荐阅读 section）
- 现有 `weekly` 类型代码保留但标记 deprecated，不删除

### D17: 增量聚类策略

**决策**：新论文先分类到已有 Theme，积累 >10 篇无法分类时触发全量重聚类。

**理由**：
- 避免每周全量重算的 LLM 成本
- Theme 对用户保持稳定（不会频繁变动）
- 新兴子领域（无法归入现有 Theme 的论文积累）会在重聚类时被识别

### D18: 方向综合用 PREMIUM Tier

**决策**：`DirectionSynthesisPipeline` 默认使用 PREMIUM tier LLM。

**理由**：
- 候选研究方向是整个系统的核心输出（「star output」）
- 需要对多个 Theme 的趋势、空白进行综合推理
- 每周仅 1 次调用，成本可控（$0.5-1/次）
- 质量优先于成本

---

## 10. 风险与缓解

### R5: LLM 聚类质量不一致

**风险**：不同批次的 LLM 调用可能产生语义重叠的聚类标签。

**缓解**：
- merge pass 专门处理合并重叠聚类
- 用户可通过 `--theme-id ... --type like/dislike` 对 Theme 反馈，指导后续聚类
- 全量重聚类定期校正

### R6: L2 分析首次成本

**风险**：~200 篇论文的首次 L2 分析估计 $4-6。

**缓解**：
- 一次性成本，后续增量处理仅 ~5-10 篇/周
- 全部缓存，重跑零成本
- 可通过 `--artifact-id` 逐条测试 prompt 质量后再全量运行

### R7: 聚类上下文窗口限制

**风险**：200 篇论文的摘要可能超出单次 LLM 上下文窗口。

**缓解**：
- 分批处理（30-40 篇/批），每批 ~4000 tokens
- merge pass 只处理聚类标签（不含论文全文），token 消耗小
- STANDARD tier 模型通常有 128K+ 上下文，单批 4K tokens 远低于限制

### R8: Theme 稳定性

**风险**：全量重聚类可能打乱用户已建立的心理模型。

**缓解**：
- `CORE` 状态的 Theme 在重聚类时保留
- Landscape 报告标注 Theme 变更（新增/合并/拆分）
- 重聚类仅影响 `CANDIDATE` 状态的 Theme

---

## 11. 实施分期

| 阶段 | 内容 | 依赖 | 新文件 | 修改文件 | Codex 工单 |
|------|------|------|--------|---------|-----------|
| **P3a** | L2 深度分析 pipeline + prompt + CLI | 无 | `pipelines/deep_analysis.py`, `prompts/deep_analysis.md` | `cli/process.py`, `cli/main.py` | 1 |
| **P3b** | Theme 模型 + Repository + 聚类 pipeline + CLI | P3a | `models/theme.py`, `repositories/theme_repository.py`, `pipelines/clustering.py`, `prompts/cluster_papers.md` | `models/enums.py`, `models/__init__.py`, `cli/process.py`, `cli/main.py` | 1-2 |
| **P3c** | 趋势分析 pipeline + CLI | P3b | `pipelines/trend_analysis.py`, `prompts/analyze_theme_trend.md` | `cli/process.py`, `cli/main.py` | 1 |
| **P3d** | CandidateDirection 模型 + Repository + 方向综合 pipeline + CLI | P3c | `models/candidate_direction.py`, `repositories/candidate_direction_repository.py`, `pipelines/direction_synthesis.py` | `models/enums.py`, `models/__init__.py`, `prompts/build_candidate_direction.md`, `cli/process.py`, `cli/main.py` | 1-2 |
| **P3e** | Landscape 报告 + 方向/主题反馈 + `run --full` | P3d | `reporting/landscape.py` | `cli/report.py`, `cli/feedback.py`, `cli/process.py`, `feedback/collector.py` | 1-2 |
| **P3f** | Profile 信号提取（反馈闭环） | P3e | `pipelines/profile_signals.py` | `prompts/extract_profile_signals.md` | 1 |

**总计**：6-9 个 Codex 工单，按依赖链串行实施。

---

## 12. 文件清单总结

### 新建文件

| 文件 | 说明 |
|------|------|
| `src/models/theme.py` | Theme ORM 模型 |
| `src/models/candidate_direction.py` | CandidateDirection ORM 模型 |
| `src/repositories/theme_repository.py` | Theme Repository |
| `src/repositories/candidate_direction_repository.py` | CandidateDirection Repository |
| `src/pipelines/deep_analysis.py` | L2 深度分析 pipeline |
| `src/pipelines/clustering.py` | 主题聚类 pipeline |
| `src/pipelines/trend_analysis.py` | 趋势分析 pipeline |
| `src/pipelines/direction_synthesis.py` | 方向综合 pipeline |
| `src/pipelines/profile_signals.py` | 反馈信号提取 pipeline |
| `src/reporting/landscape.py` | Landscape 报告生成器 |
| `prompts/deep_analysis.md` | L2 深度分析 prompt |
| `prompts/cluster_papers.md` | 聚类 prompt |
| `prompts/analyze_theme_trend.md` | 趋势分析 prompt |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/models/enums.py` | 新增 `ThemeStatus`, `DirectionStatus` |
| `src/models/__init__.py` | 导入新模型 |
| `src/cli/main.py` | 注册新命令 |
| `src/cli/process.py` | 新增 `deep-analyze`, `cluster`, `trend`, `synthesize` 命令 + `run --full` |
| `src/cli/feedback.py` | 新增 `--theme-id`, `--direction-id` 互斥选项 |
| `src/cli/report.py` | 新增 `landscape` 报告类型 |
| `src/feedback/collector.py` | 新增 `collect_theme_feedback()`, `collect_direction_feedback()` |
| `prompts/build_candidate_direction.md` | 填充（当前为空） |
| `prompts/extract_profile_signals.md` | 填充（当前为空） |
