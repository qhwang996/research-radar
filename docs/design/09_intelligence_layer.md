# Intelligence Layer - 研究情报分析 (v2: 双轨架构)

> **v2 变更说明 (2026-03-16)**：从单一 LLM 分析链重构为双轨处理 + 空白检测架构。
> 核心转变：从「用已知兴趣过滤论文」到「发现学术覆盖与工业需求之间的空白」。
> 已完成的 P3a（L2 深度分析）和 P3b（主题聚类）保留不改，作为学术轨的核心组件。

## 1. 设计背景

### 1.1 Phase 1-2 回顾

Research Radar Phase 1-2 建立了完整的数据基座：爬取→归一化→L1 增强→相关度评分→排序→报告。

### 1.2 v1 架构的问题

v1 智能分析层设计了一条线性 LLM 链：`deep-analyze → cluster → trend → synthesize`。review 后发现三个根本问题：

1. **只能过滤已知兴趣，不能发现未知机会**。Profile 有 30 个具体关键词（xss, csrf, ssrf 等），系统只会返回这些关键词匹配的内容。但用户要找的「高门槛、竞争少但有意义」的方向，往往不在已知关键词覆盖范围内。

2. **不同来源的结构性差异被拍平**。顶会论文（学术界在做什么）和博客（工业界在痛什么）用同一套 `final_score = recency×0.4 + authority×0.3 + relevance×0.3` 排序。它们的作用根本不同，不应混排。

3. **纯 LLM 长链推理不可靠**。四步 LLM 链每步都只有 Haiku 可用，误差逐级累积。方向综合（最终输出）的质量高度依赖前面每一步的准确性。

### 1.3 用户目标精炼

用户（安全领域低年级博士）的研究方向选择偏好：
- **高门槛**：技术难度大，需要深入的前置知识
- **长周期**：适合博士阶段的深耕，非短期热点
- **低竞争**：做的人少，能避免与大组正面竞争
- **有意义**：有实际影响力，能发表高质量论文

这种方向往往出现在**工业界已在痛但学术界尚未充分解决**的空白地带。

### 1.4 信息源的层次结构

| 层级 | 来源 | 特征 | 信号类型 |
|------|------|------|---------|
| T1 最权威最慢 | 四大顶会 | 经同行评审，1-2 年时滞 | 学术界已确立的研究方向 |
| T2 较权威较新 | arXiv | 未经评审，最新研究 | 趋势萌芽，新兴方向 |
| T3 权威+新潮 | Project Zero / PortSwigger / Cloudflare | 机构背书，实际攻击面 | 工业需求信号 |
| T4 快但不权威 | 个人博客 / 公众号 | 实时热点，质量参差 | 快速热点信号 |

**关键洞察**：不同层级的信息应分轨处理、各自产出，最后交叉比对——而非拍平排序。

---

## 2. 总体架构（v2）

### 2.1 双轨 + 空白检测

```
                      INGEST (不变)
                 crawl → normalize → enrich(L1)
                           |
             +-------------+-------------+
             |                           |
        ACADEMIC TRACK              INDUSTRY TRACK
        (T1 顶会 + T2 arXiv)       (T3 研究博客 + T4 未来快速源)
             |                           |
        broad domain filter         broad domain filter
             |                           |
        L2 deep-analyze (已有)      signal-extract (新)
             |                           |
        cluster (已有)              demand signal 聚合
             |                           |
        stat trend                       |
             |                           |
             +-------------+-------------+
                           |
                     GAP DETECTOR (新)
                学术覆盖 vs 工业需求 的交叉比对
                           |
                     DIRECTION SYNTHESIS (改造)
                基于空白 + Profile偏好 推导方向
                           |
                     LANDSCAPE REPORT
```

### 2.2 数据流概览

```
T1+T2 学术论文 (~2000 篇域内)     T3+T4 行业博客 (~100 篇)
        |                                 |
   L2 深度分析                        需求信号提取
   (问题/方法/局限/开放问题)          (问题/影响/方案缺口/紧迫性)
        |                                 |
   10-15 个 Theme                    需求信号聚合
   (研究子领域)                       (工业界在痛什么)
        |                                 |
   每个 Theme 的趋势                      |
        |                                 |
        +---------- 空白检测 ------------+
                      |
            「工业界在痛，学术界没解决好」的空白
                      |
                 2-3 个候选方向
             (含证据链 + 空白评分)
                      |
               Landscape 全景报告
```

### 2.3 与 v1 的关键差异

| 维度 | v1 | v2 |
|------|-----|-----|
| 信息处理 | 所有来源拍平排序 | 学术轨 / 工业轨分开处理 |
| 过滤方式 | 30 个具体关键词精确匹配 | 宽泛领域过滤，允许发现未知 |
| 方向发现 | 纯 LLM 链推理 | 统计空白检测 + LLM 验证 |
| 核心信号 | 论文内容（开放问题） | 学术覆盖 × 工业需求的差距 |
| arXiv | 未接入 | cs.CR + cs.SE + cs.PL |
| 博客作用 | 和论文混排 | 独立的需求信号源 |

---

## 3. 数据模型

### 3.1 Source Tier 正式化

新增 `SourceTier` 和 `InformationTrack` 枚举（`src/models/enums.py`）：

```python
class SourceTier(str, Enum):
    T1_CONFERENCE = "t1-conference"        # 四大顶会
    T2_ARXIV = "t2-arxiv"                 # arXiv
    T3_RESEARCH_BLOG = "t3-research-blog"  # Project Zero, PortSwigger, Cloudflare
    T4_PERSONAL = "t4-personal"            # 未来: 个人博客、公众号

class InformationTrack(str, Enum):
    ACADEMIC = "academic"    # T1 + T2
    INDUSTRY = "industry"    # T3 + T4
```

不需要 schema 迁移。现有 `Artifact.source_tier` 列是 `String(50)`，直接存新枚举值。已有数据需一次性迁移：`"top-tier" → "t1-conference"`，`"high-quality-blog" → "t3-research-blog"` 等。

### 3.2 Theme（研究子领域）— 已实现，不变

表名：`themes`，文件：`src/models/theme.py`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| theme_id | String(36), unique, indexed | UUID 业务主键 |
| name | String(200) | 主题名称 |
| description | Text | 2-3 句话描述 |
| keywords | JSON (list[str]) | 代表性关键词 |
| artifact_ids | JSON (list[int]) | 关联论文的 artifact.id |
| artifact_count | Integer | 论文数量 |
| paper_count_by_year | JSON (dict[str,int]) | 按年统计 |
| methodology_tags | JSON (list[str]) | 常见研究方法 |
| open_questions | JSON (list[str]) | 开放问题 |
| trend_direction | String(20) | `growing` / `stable` / `declining` |
| status | Enum(ThemeStatus) | `candidate` / `core` / `archived` |
| generation_version | String(50) | 聚类版本 |
| week_id | String(10) | ISO 周 |
| created_at / updated_at | DateTime | 时间戳 |

### 3.3 CandidateDirection（候选研究方向）— 改造

在 v1 基础上新增 `gap_id` 和 `gap_score` 字段，关联空白检测输出：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| direction_id | String(36), unique, indexed | UUID 业务主键 |
| title | String(300) | 方向标题 |
| description | Text | 3-5 句话描述 |
| rationale | Text | 为什么有价值 |
| why_now | Text | 为什么时机合适 |
| **gap_id** | **String(36), nullable** | **关联的 ResearchGap ID（新增）** |
| **gap_score** | **Float, nullable** | **空白评分（新增）** |
| related_theme_ids | JSON (list[str]) | 关联的 theme_id |
| supporting_artifact_ids | JSON (list[int]) | 支撑 artifact.id（论文 + 博客） |
| key_papers | JSON (list[dict]) | `[{title, artifact_id, contribution}]` |
| open_questions | JSON (list[str]) | 待解决问题 |
| novelty_score | Float, nullable | 新颖性 |
| impact_score | Float, nullable | 影响力 |
| feasibility_score | Float, nullable | 可行性 |
| **barrier_score** | **Float, nullable** | **门槛高度（新增，用户偏好高门槛）** |
| composite_direction_score | Float, nullable | 加权综合分 |
| status | Enum(DirectionStatus) | `active` / `under_review` / `archived` |
| generation_version | String(50) | 版本号 |
| week_id | String(10) | ISO 周 |
| created_at / updated_at | DateTime | 时间戳 |

### 3.4 ResearchGap（研究空白）— 新增

表名：`research_gaps`，文件：`src/models/research_gap.py`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| gap_id | String(36), unique, indexed | UUID 业务主键 |
| topic | String(300) | 空白主题描述 |
| demand_signals | JSON (list[dict]) | `[{artifact_id, problem_described, source_name}]` |
| demand_frequency | Integer | 有多少个独立来源提到 |
| academic_coverage | Float | 0.0-1.0，学术界覆盖程度 |
| gap_score | Float | `demand_frequency × (1 - academic_coverage)` |
| related_theme_ids | JSON (list[str]) | 最相近的学术 Theme |
| related_artifact_ids | JSON (list[int]) | 相关的论文 + 博客 artifact |
| status | String(20) | `active` / `validated` / `dismissed` |
| generation_version | String(50) | 版本号 |
| week_id | String(10) | ISO 周 |
| created_at / updated_at | DateTime | 时间戳 |

### 3.5 Profile V2（用户画像改造）

Profile 模型新增两个 JSON 字段（nullable，无 schema 迁移）：

```python
# src/models/profile.py 新增字段
domain_scope: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
direction_preferences: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

新版 seed profile (`data/seed_profile_v2.json`)：

```json
{
  "profile_version": "v2-broad",
  "current_research_area": "Software Security & Systems Security",
  "interests": [
    "Vulnerability detection", "Program analysis", "Fuzzing",
    "Supply chain security", "Web application security"
  ],
  "domain_scope": ["security", "software-engineering", "programming-languages"],
  "preferred_topics": [],
  "avoided_topics": [
    "cryptography-theory", "blockchain", "formal-verification",
    "privacy-policy", "usable-security-survey", "network-protocol-theory",
    "quantum-computing"
  ],
  "direction_preferences": {
    "barrier_level": "high",
    "technical_depth": "deep",
    "competition_tolerance": "low",
    "cycle_preference": "long",
    "impact_type": "practical"
  },
  "primary_goals": [
    "找到高门槛、技术深度大、竞争少但有实际影响力的研究方向",
    "偏好长周期有意义的工作，回避拥挤方向"
  ],
  "evaluation_criteria": {
    "must_have": "明确的技术贡献或新攻击面",
    "nice_to_have": "有原型实现或实际影响证据",
    "dealbreaker": "纯理论无应用场景"
  },
  "is_active": true
}
```

**关键变化**：`preferred_topics` 清空。不再用具体关键词约束发现范围。

### 3.6 现有模型变更

`Artifact.summary_l2`（Text, nullable）双用途：
- 论文类 artifact：存 L2 深度分析 JSON（已有格式不变）
- 博客类 artifact：存需求信号 JSON（新格式，通过 `source_type` 区分）

### 3.7 Repository

| Repository | 文件 | 说明 |
|------------|------|------|
| `ThemeRepository` | `src/repositories/theme_repository.py` | 已实现 |
| `ResearchGapRepository` | `src/repositories/research_gap_repository.py` | 新建 |
| `CandidateDirectionRepository` | `src/repositories/candidate_direction_repository.py` | 新建 |

---

## 4. Pipeline 详细设计

### 4.1 DeepAnalysisPipeline（L2 深度分析）— 已实现，不变

**文件**：`src/pipelines/deep_analysis.py`

**作用域**：学术轨（T1 + T2 论文）。

筛选条件、输出格式、LLM 配置均不变。详见 v1 设计。

**v2 变更**：`min_relevance` 门槛从 0.6 降到 0.4（配合 Profile 放宽后更多论文进入分析）。

### 4.2 ClusteringPipeline（主题聚类）— 已实现，不变

**文件**：`src/pipelines/clustering.py`

**作用域**：学术轨（仅论文）。代码中已有 `source_type == SourceType.PAPERS` 过滤，博客不会进入聚类。

### 4.3 SignalExtractionPipeline（需求信号提取）— 新增

**文件**：`src/pipelines/signal_extraction.py`

**作用域**：工业轨（T3 + T4 博客）。

**目的**：从博客文章中提取结构化需求信号——工业界遇到了什么问题、现有方案有什么缺口。

**筛选条件**：
- `source_type == SourceType.BLOGS`
- `relevance_score >= 0.3`（博客门槛比论文更低，因为即使边缘相关也可能揭示需求信号）
- `summary_l2 IS NULL`

**输出格式**（JSON 字符串存入 `summary_l2`）：

```json
{
  "signal_type": "demand",
  "problem_described": "文章描述的核心安全问题",
  "affected_systems": ["受影响的系统/技术"],
  "current_solutions": "现有解决方案（如果提到）",
  "solution_gaps": ["现有方案的不足之处"],
  "urgency_indicators": ["为什么现在重要"],
  "related_academic_topics": ["相关学术研究主题"]
}
```

`signal_type: "demand"` 字段用于区分博客信号 JSON 和论文 L2 分析 JSON。

**LLM 配置**：
- Tier: STANDARD
- max_tokens: 1000
- temperature: 0.3
- max_workers: 4
- prompt 模板：`prompts/extract_demand_signal.md`（中文）
- cache_key: `signal_{signal_version}_{canonical_id}`

**架构模式**：复用 `DeepAnalysisPipeline` 的 ThreadPoolExecutor + LLMClient 模式。

### 4.4 TrendAnalysisPipeline（趋势分析）— 设计改造

**文件**：`src/pipelines/trend_analysis.py`

**作用域**：学术轨 Theme。

**v2 变更**：增加 arXiv 论文的新关键词涌现检测。

**处理逻辑**：

1. **定量分析**（纯计算，无 LLM）：
   - 按年统计论文数 → `paper_count_by_year`
   - `trend_direction`：近 2 年 vs 前 2 年论文数对比
   - **新增**：arXiv 近 6 个月新出现的关键词/概念检测（从 L2 的 `related_concepts` 中提取，与 12 个月前对比）

2. **定性分析**（LLM，可选）：
   - 每个 Theme 的方法论演进总结
   - 高频 limitation/open_question 归纳

### 4.5 GapDetectionPipeline（空白检测）— 新增，核心

**文件**：`src/pipelines/gap_detection.py`

**目的**：交叉比对学术覆盖和工业需求，找出空白。

**算法**（主要是统计，少量 LLM）：

**Step 1: 构建学术覆盖图**
- 输入：所有 Theme（含 keywords, methodology_tags, open_questions）+ 所有论文 L2 的 `related_concepts`
- 产出：一个 topic → coverage_count 映射，表示「学术界已覆盖的主题」

**Step 2: 构建工业需求图**
- 输入：所有博客 demand signal 的 `related_academic_topics` + `solution_gaps`
- 产出：一个 topic → demand_frequency 映射，表示「工业界需要解决的问题」
- 按 frequency 排序：多个独立来源提到的问题更可信

**Step 3: 计算覆盖空白**
- 对每个工业需求 topic，查找学术覆盖图中的匹配度
- `gap_score = demand_frequency × (1 - academic_coverage_ratio)`
- 高 gap_score = 工业需求强但学术覆盖弱

**Step 4: LLM 验证（可选，单次调用）**
- 取 top-N 空白候选
- 一次 LLM 调用：「这些是真实的研究空白吗？哪些适合博士级研究？」
- 这是一次验证，不是多步推理

**输出**：`ResearchGap` 记录列表，持久化到 `research_gaps` 表。

**LLM 配置**：
- 验证调用 Tier: PREMIUM（核心输出质量优先）
- max_tokens: 3000
- temperature: 0.3
- prompt 模板：`prompts/detect_gaps.md`（中文）
- cache_key: `gap_{gap_version}_{week_id}_{sha256(demand_topics + academic_coverage)}`

**关键优势**：Steps 1-3 是纯统计，即使 Haiku 的 L2 分析和信号提取有误差，统计聚合会平滑个体错误。LLM 只在最后做验证，不做多步推理。

### 4.6 DirectionSynthesisPipeline（方向综合）— 改造

**文件**：`src/pipelines/direction_synthesis.py`

**v2 变更**：输入从 Themes 改为 ResearchGaps + Themes + Profile.direction_preferences。

**输入**：
- Top-N ResearchGap（含 gap_score, demand_signals, academic_coverage）
- 相关 Theme（含 trend_direction, open_questions）
- Profile.direction_preferences（barrier_level, competition_tolerance 等）
- 历史反馈

**输出**：
- 2-3 个 `CandidateDirection` 记录，每个包含：
  - title, description, rationale, why_now
  - **gap_id** + **gap_score**（来自空白检测的证据）
  - 四维评分（novelty, impact, feasibility, **barrier**）
  - 支撑 artifact（论文 + 博客）
  - key_papers
  - open_questions

**prompt 应特别关注**：
1. 哪些空白代表高门槛研究机会？
2. 哪些有长期意义 vs 短期热点？
3. 博士生是否可行（时间、资源约束）？

**LLM 配置**：
- Tier: PREMIUM
- max_tokens: 4000
- temperature: 0.5
- prompt 模板：`prompts/synthesize_from_gaps.md`（中文，新建）
- 单次调用，有结构化统计数据作为输入

---

## 5. 评分改造

### 5.1 分轨评分

v1 用同一公式 `final_score = recency×0.4 + authority×0.3 + relevance×0.3` 打所有来源。v2 分轨：

**学术轨**（T1 + T2 论文）：
```
academic_score = domain_relevance × 0.5 + recency × 0.3 + authority × 0.2
```
- `domain_relevance`：宽泛领域相关度（替代原来的窄 `relevance_score`）
- authority 权重降低（T1 论文全是 1.0，区分度低）
- 此分用于决定哪些论文进入 L2 分析，不用于论文 vs 博客排序

**工业轨**（T3 + T4 博客）：
```
industry_score = recency × 0.5 + domain_relevance × 0.4 + authority × 0.1
```
- recency 权重最高（博客时效性是核心价值）
- authority 极低（T3 博客都是经筛选的，区分度小）

### 5.2 相关度评分 v4

`RelevanceStrategy` 改造：

- `preferred_topics` 为空时，跳过 keyword match 组件
- `relevance_score` 完全由 LLM domain filter 决定
- LLM prompt 从「这跟 web-security 相关吗？」变为「这是安全/软件工程领域的吗？」

新 prompt（`prompts/relevance_score_v4.md`）：

```
你正在为一位安全与软件工程领域博士研究生评估内容的领域相关度。

注意：这是宽泛的领域过滤，不是窄主题匹配。目标是保留该领域内所有可能有价值的内容。

用户领域范围：{{domain_scope}}
回避主题：{{avoided_topics}}

评分标准（1-5）：
5 = 安全或软件工程核心问题（漏洞、攻击、防御、程序分析、软件测试等）
4 = 安全或软件工程的重要子领域（移动安全、内核安全、编译器安全等）
3 = 与安全/SE 有明确交叉的其他领域（AI 安全应用、网络测量等）
2 = 边缘相关（纯系统性能优化、纯机器学习等）
1 = 不相关或属于回避列表

内容信息：
标题：{{title}}
来源：{{source_name}} ({{source_tier}})
摘要：{{summary_l1}}
标签：{{tags}}

请只返回一个 JSON：
{"score": 数字, "reason": "一句话理由"}
```

**影响**：全量 re-score（v4 cache key），约 3900+55 条，Haiku 成本 ~$0.50。

---

## 6. Landscape 全景报告（v2）

### 6.1 新增「空白分析」section

在「趋势洞察」和「候选研究方向」之间新增：

```markdown
---

## 学术-工业空白分析

以下是工业界已在关注但学术界尚未充分解决的领域：

### 空白 1: [Topic]  (gap_score: X.XX)
- **工业需求**: N 个独立来源提到
  - [Blog A] (PortSwigger) — 描述了什么问题...
  - [Blog B] (Project Zero) — 发现了什么...
- **学术覆盖**: 当前覆盖度 XX%
  - 最近相关的 Theme: [Theme Name]
  - 但缺少: ...
- **空白性质**: 为什么这是一个研究机会

### 空白 2: [Topic]  (gap_score: X.XX)
...

---
```

### 6.2 报告完整结构

```
1. 研究前沿地图（Theme 概览，含趋势）
2. 趋势洞察（上升领域、方法论演进）
3. 学术-工业空白分析（新增，核心 section）
4. 候选研究方向（基于空白，含证据链）
5. 推荐阅读（支撑方向的论文 + 博客）
6. 博客回顾
7. 统计
```

---

## 7. CLI 集成

### 7.1 新增命令

| 命令 | 说明 | 关键参数 |
|------|------|----------|
| `deep-analyze` | L2 深度分析（已有） | `--provider`, `--artifact-id`, `--workers 4`, `--min-relevance 0.4` |
| `cluster` | 主题聚类（已有） | `--provider`, `--full/--incremental`, `--min-relevance 0.4` |
| `extract-signals` | 博客需求信号提取（新） | `--provider`, `--workers 4`, `--min-relevance 0.3` |
| `trend` | 趋势分析 | `--provider`, `--theme-id` |
| `detect-gaps` | 空白检测（新） | `--provider`, `--top-n 10` |
| `synthesize` | 方向综合 | `--provider`, `--week-id` |

### 7.2 `run --full` 扩展

```bash
# 完整智能分析链（每周运行）
research-radar run --full --provider anthropic
```

执行顺序：
```
crawl → normalize → enrich → llm-relevance(v4) → score
  → deep-analyze (学术轨)
  → extract-signals (工业轨)
  → cluster
  → trend
  → detect-gaps (交叉比对)
  → synthesize
  → landscape-report
```

---

## 8. Prompt 模板

### 8.1 新建模板

| 文件 | 用途 | 语言 |
|------|------|------|
| `prompts/relevance_score_v4.md` | 宽泛领域相关度评分 | 中文 |
| `prompts/extract_demand_signal.md` | 博客需求信号提取 | 中文 |
| `prompts/detect_gaps.md` | 空白验证 | 中文 |
| `prompts/synthesize_from_gaps.md` | 基于空白的方向综合 | 中文 |
| `prompts/analyze_theme_trend.md` | 趋势分析 | 中文 |

### 8.2 已有模板

| 文件 | 状态 |
|------|------|
| `prompts/deep_analysis.md` | 已有，不变 |
| `prompts/cluster_papers.md` | 已有，不变 |
| `prompts/relevance_score.md` | 保留（v3），v4 新建单独文件 |

---

## 9. 运行环境配置

### 9.1 LLM Tier 降级

不变。所有 tier 在运行时统一映射到 haiku。代码中的 tier 标注保留，后续升级只需改环境变量。

### 9.2 成本估算（v2，基于 haiku）

| 阶段 | Tier | 调用次数 | 估算成本 |
|------|------|---------|---------|
| 相关度 re-score (v4) | STANDARD | ~4000（一次性） | ~$0.50 |
| L2 深度分析 | STANDARD | ~500-800（一次性，论文量增加） | ~$0.40 |
| 需求信号提取 | STANDARD | ~55（现有博客）+ 增量 | ~$0.05 |
| 聚类 | STANDARD + STANDARD | 10-20 批 + 1 merge | ~$0.10 |
| 趋势分析 | STANDARD | 10-15 Theme | ~$0.05 |
| 空白检测 | PREMIUM | 1 次 | ~$0.01 |
| 方向综合 | PREMIUM | 1 次 | ~$0.01 |

**首次运行总成本**：约 $1.10（主要是 re-score 和 L2 分析）
**每周增量成本**：约 $0.15

---

## 10. 设计决策

### D13-D18: 保留

v1 的 D13（LLM 聚类）、D14（L2 存 summary_l2）、D15（Theme 快照）、D16（Landscape 替换周报）、D17（增量聚类）、D18（方向综合用 PREMIUM）保留。

### D19: 双轨处理 > 拍平排序

**决策**：学术来源和工业来源分轨处理，各自产出不同类型的中间结果，最后交叉比对。

**理由**：
- 论文告诉你「学术界在做什么」，博客告诉你「工业界在痛什么」
- 拍平排序会丧失这种结构性差异
- 空白检测需要两条轨道的独立产出才能交叉比对

### D20: 统计空白检测 > 纯 LLM 推理链

**决策**：方向发现的核心用统计方法（词频交叉比对），LLM 只做最后验证。

**理由**：
- Haiku 推理能力有限，四步 LLM 链误差会累积
- 统计方法对个体 LLM 输出错误有天然容错（聚合平滑）
- 用结构化统计数据喂给 LLM 做一次验证，比让 LLM 自己从头推理更可靠
- 减少 LLM 调用次数，降低成本和延迟

### D21: Profile 放宽为领域过滤

**决策**：清空 `preferred_topics`，只保留 `domain_scope` + `avoided_topics` 做宽泛过滤。

**理由**：
- 30 个具体关键词限制了发现范围
- 用户要找「不知道自己会感兴趣的」方向
- 安全/SE 大领域内的内容全部保留，由下游分析决定价值
- 已有 `avoided_topics` 足够排除明确不相关的内容

**影响**：re-score 全量数据（v4），成本 ~$0.50。进入分析的论文数从 ~200 增到 ~500-800。

### D22: 需求信号存 summary_l2

**决策**：博客 demand signal JSON 存入 `Artifact.summary_l2`，与论文 L2 JSON 共用字段。

**理由**：
- 避免 schema 迁移
- 通过 `signal_type` 字段和 `source_type` 区分两种 JSON 格式
- 博客语料少（~55 条），无需独立表

**权衡**：下游解析需检查 `source_type`，增加一点复杂度。

### D23: 轨道分离是逻辑分离，非物理分离

**决策**：两条轨道共用 `artifacts` 表，分离在 pipeline 路由和评分权重中实现。

**理由**：
- 简单，不增加表数量
- 支持跨轨查询（如「找到与这个博客需求信号相关的论文」）
- `source_tier` 字段足够做路由判断

---

## 11. 风险与缓解

### R5-R8: 保留

v1 的 R5（聚类质量）、R6（L2 首次成本）、R7（上下文窗口）、R8（Theme 稳定性）保留。

### R9: 空白检测的词汇匹配精度

**风险**：统计交叉比对基于 keyword/topic 字符串匹配，可能漏掉语义相同但措辞不同的匹配。

**缓解**：
- `related_academic_topics`（博客端）和 `keywords` + `related_concepts`（学术端）都由 LLM 生成，LLM 会倾向使用规范术语
- 匹配时做 lowercase + stem 处理
- 可选：用 LLM 做一次语义匹配增强（成本可控，一次调用）

### R10: arXiv 数据量过大

**风险**：cs.CR + cs.SE + cs.PL 合计约 5000-8000 篇/年。

**缓解**：
- 宽泛 domain filter 会过滤掉大部分（预计 ~60% 不在安全/SE 交叉领域）
- L2 深度分析只处理 relevance >= 0.4 的论文
- SQLite 处理万级记录无压力

### R11: 需求信号质量依赖博客数量

**风险**：当前只有 55 篇博客，需求信号可能不够多样化。

**缓解**：
- 先用现有 55 篇验证 pipeline，用户后续提供更多源
- 需求信号是增量积累的，博客源越多信号越丰富
- 空白检测算法本身很轻量，随时可重跑

---

## 12. 实施分期

### Phase A: 基础改造

| 工单 | 内容 | 依赖 | 新文件 | 修改文件 |
|------|------|------|--------|---------|
| **A1** | SourceTier 枚举 + 数据迁移 | 无 | — | `enums.py`, `normalization.py`, `authority.py`, `recency.py`, `cli/process.py` |
| **A2** | Profile V2 + 宽泛相关度 | 无 | `seed_profile_v2.json`, `prompts/relevance_score_v4.md` | `profile.py`, `relevance.py`, `llm_relevance.py` |
| **A3** | arXiv 爬虫 | A1 | `crawlers/arxiv_crawler.py` | `registry.py`, `cli/crawl.py` |

A1 和 A2 可并行。

### Phase B: 工业信号轨道

| 工单 | 内容 | 依赖 | 新文件 | 修改文件 |
|------|------|------|--------|---------|
| **B1** | 需求信号提取 pipeline | A1 | `pipelines/signal_extraction.py`, `prompts/extract_demand_signal.md` | `cli/process.py`, `cli/main.py` |
| **B2** | 分轨评分 | A1, A2 | `pipelines/track_router.py` | `composite.py` |

### Phase C: 空白检测（核心产出）

| 工单 | 内容 | 依赖 | 新文件 | 修改文件 |
|------|------|------|--------|---------|
| **C1** | ResearchGap 模型 + 空白检测 pipeline | B1, B2 | `models/research_gap.py`, `repositories/research_gap_repository.py`, `pipelines/gap_detection.py`, `prompts/detect_gaps.md` | `enums.py`, `models/__init__.py`, `cli/process.py` |
| **C2** | CandidateDirection 模型 + 改造方向综合 | C1 | `models/candidate_direction.py`, `repositories/candidate_direction_repository.py`, `pipelines/direction_synthesis.py`, `prompts/synthesize_from_gaps.md` | `enums.py`, `models/__init__.py`, `cli/process.py` |
| **C3** | Landscape 报告 | C2 | `reporting/landscape.py` | `cli/report.py`, `cli/process.py` |

### Phase D: 趋势 + 反馈

| 工单 | 内容 | 依赖 | 新文件 | 修改文件 |
|------|------|------|--------|---------|
| **D1** | 统计趋势分析 | Phase A | `pipelines/trend_analysis.py`, `prompts/analyze_theme_trend.md` | `cli/process.py` |
| **D2** | 反馈闭环 | C3 | `pipelines/profile_signals.py` | `cli/feedback.py`, `prompts/extract_profile_signals.md` |

### 依赖图

```
A1 (tier) ──→ A3 (arXiv) ──→ B2 (分轨评分) ──→ C1 (空白检测)
    |                                                  |
    └──→ A2 (Profile V2) ──→ B1 (信号提取) ──→ C2 (方向综合)
                                                       |
                                                 C3 (Landscape)
                                                       |
                                              D1 (趋势) + D2 (反馈)
```

**总计**：约 10 个 Codex 工单。

---

## 13. 文件清单总结

### 新建文件

| 文件 | 说明 | Phase |
|------|------|-------|
| `src/crawlers/arxiv_crawler.py` | arXiv 爬虫 | A3 |
| `src/models/research_gap.py` | ResearchGap ORM 模型 | C1 |
| `src/models/candidate_direction.py` | CandidateDirection ORM 模型 | C2 |
| `src/repositories/research_gap_repository.py` | ResearchGap Repository | C1 |
| `src/repositories/candidate_direction_repository.py` | CandidateDirection Repository | C2 |
| `src/pipelines/signal_extraction.py` | 需求信号提取 | B1 |
| `src/pipelines/track_router.py` | 轨道路由 | B2 |
| `src/pipelines/gap_detection.py` | 空白检测 | C1 |
| `src/pipelines/direction_synthesis.py` | 方向综合 | C2 |
| `src/pipelines/trend_analysis.py` | 趋势分析 | D1 |
| `src/pipelines/profile_signals.py` | 反馈信号提取 | D2 |
| `src/reporting/landscape.py` | Landscape 报告 | C3 |
| `data/seed_profile_v2.json` | 宽泛 Profile | A2 |
| `prompts/relevance_score_v4.md` | 宽泛相关度 prompt | A2 |
| `prompts/extract_demand_signal.md` | 需求信号提取 prompt | B1 |
| `prompts/detect_gaps.md` | 空白验证 prompt | C1 |
| `prompts/synthesize_from_gaps.md` | 方向综合 prompt | C2 |
| `prompts/analyze_theme_trend.md` | 趋势分析 prompt | D1 |

### 修改文件

| 文件 | 改动 | Phase |
|------|------|-------|
| `src/models/enums.py` | 新增 SourceTier, InformationTrack, DirectionStatus | A1 |
| `src/models/profile.py` | 新增 domain_scope, direction_preferences 字段 | A2 |
| `src/models/__init__.py` | 导入新模型 | C1 |
| `src/pipelines/normalization.py` | 更新 tier 映射 | A1 |
| `src/scoring/relevance.py` | 处理空 preferred_topics | A2 |
| `src/scoring/composite.py` | 分轨权重 | B2 |
| `src/scoring/authority.py` | 用 SourceTier 枚举 | A1 |
| `src/scoring/recency.py` | 用 SourceTier 枚举 | A1 |
| `src/pipelines/llm_relevance.py` | bump v4 | A2 |
| `src/crawlers/registry.py` | 注册 ArxivCrawler | A3 |
| `src/cli/process.py` | 新增命令 + run --full | B1, C1 |
| `src/cli/main.py` | 注册命令 | B1, C1 |
| `src/cli/report.py` | landscape 类型 | C3 |
| `src/cli/feedback.py` | theme/direction 反馈 | C3 |

### 保留不变的文件

| 文件 | 原因 |
|------|------|
| `src/pipelines/deep_analysis.py` | 学术轨 L2 分析，完全复用 |
| `src/pipelines/clustering.py` | 学术轨聚类，完全复用 |
| `src/pipelines/enrichment.py` | L1 摘要，轨道无关 |
| `src/models/artifact.py` | 无 schema 变更 |
| `src/models/theme.py` | 已实现，不变 |
| 现有 7 个爬虫 | 不变 |
