# Iteration Plan

本文档按优先级定义实现计划，而非严格时间表。

---

## 实现原则

1. **按优先级，不按时间**：完成一个模块立即进入下一个
2. **最小可用优先**：先实现核心功能，可选功能后续补充
3. **模块化开发**：每个模块独立可测试
4. **持续集成**：每完成一个模块就集成测试

---

## Priority 0: 基础设施（必须最先完成）

### P0.1 数据库模型 ✅ 已完成（2026-03-09）
**依赖**：无
**核心功能**：
- ✅ Artifact模型（title, authors, year, source_type, scores）
- ✅ Feedback模型（target_type, target_id, feedback_type, content）
- ✅ Profile模型（interests, preferences）
- ✅ Repository层（BaseRepository + 3个具体Repository）
- ✅ 数据库基础设施（Base, TimestampedModel, session管理）
- ✅ 自定义异常
- ✅ 单元测试（6 passed）

**可选功能**：
- ⏭️ Theme模型（Phase 1可以不要）
- ⏭️ CandidateDirection模型（Phase 1可以简化）
- ⏭️ TrackingHistory模型（Phase 2）
- ⏭️ Alembic迁移（Phase 2）

**验收标准**：
- ✅ 数据库可以创建
- ✅ 可以CRUD操作
- ✅ 有基础测试

**实现亮点**：
- 使用SQLAlchemy 2.0现代语法
- 泛型BaseRepository设计优秀
- 测试覆盖完整

**已知问题**：
- 无Alembic迁移（Phase 1可接受，使用create_all()）

---

## Priority 1: 数据采集（核心流程第一步）

### P1.1 爬虫基类和整合 ✅ 已完成（2026-03-09）
**依赖**：无
**核心功能**：
- ✅ BaseCrawler接口定义（base.py, 262行）
- ✅ 四大顶会爬虫：NDSS, S&P, CCS, USENIX Security
- ✅ 3个博客爬虫：Cloudflare Blog, PortSwigger, Google Project Zero
- ✅ 统一的数据保存格式（JSON）
- ✅ 错误处理和日志（重试机制、session管理）
- ✅ 爬虫注册机制（registry.py）
- ✅ 单元测试（10 passed）

**可选功能**：
- ⏭️ arXiv爬虫（后续添加）
- ⏭️ 更多博客源（后续添加）

**验收标准**：
- ✅ 能爬取四大顶会多年数据
- ✅ 能爬取3个博客的最新文章
- ✅ 数据保存为统一JSON格式
- ✅ 有完整的错误处理和日志
- ✅ 有单元测试

**实现亮点**：
- 完整的重试机制（Retry with backoff）
- 统一的session管理和工具函数
- 爬虫注册机制便于扩展
- 向后兼容（v2版本变成别名）

**已知问题**：
- CCS数据源不稳定（已通过DBLP fallback缓解）
- 博客模板可能漂移（已通过live validation修复）

---

## Priority 2: 数据处理（核心流程第二步）

### P2.1 Normalization Pipeline ✅ 已完成（2026-03-10）
**依赖**：P0.1, P1.1
**核心功能**：
- ✅ 读取 raw JSON（支持单文件、目录、递归扫描）
- ✅ 兼容 legacy `papers/articles` 和 current `items` 格式
- ✅ 转换为 Artifact 对象
- ✅ 生成稳定 canonical_id（UUID5）
- ✅ 基础去重（基于 title key + source context）
- ✅ upsert 保存到数据库
- ✅ 对现有 `data/raw/papers` 试跑成功
- ✅ RawFetch追踪模型和Repository
- ✅ 按文件记录 `file_path/content_hash/source/item_count/status`
- ✅ 增量处理（已处理且内容未变的文件自动跳过）
- ✅ 文件内容变化后自动重新处理并刷新统计

验收标准：
- [x] RawFetch模型实现
- [x] RawFetchRepository实现
- [x] NormalizationPipeline集成RawFetch追踪
- [x] 增量处理有效（已处理的文件被跳过）
- [x] 文件变化后重新处理（content_hash变化）
- [x] 单元测试

**实现亮点**：
- 支持历史 raw 数据重放，不需要迁移旧文件
- 兼容论文和博客两类输入
- 真实数据试跑完成：1499 条 raw 记录归一化后落成 1168 条 artifact
- RawFetch 支持文件级 `content_hash` 增量跳过
- `normalize_version` 已进入 RawFetch 追踪，后续版本升级可强制重处理
- 全量测试通过（23 passed）

**已知问题**：
- 当前去重仍是 MVP 级别，主要依赖 title key，不包含复杂 alias mapping
- raw 文件内容删减时，当前不会自动回收旧 artifact，需要后续补 tombstone/cleanup 机制

### P2.2 LLM服务层 ✅ 已完成（2026-03-11）
**依赖**：无
**核心功能**：
- ✅ `LLMClient` 封装（provider 选择、tier -> model 映射、usage 记录）
- ✅ OpenAI Responses API 适配器
- ✅ Anthropic Messages API 适配器
- ✅ 基础缓存（本地 JSON 文件缓存）
- ✅ 重试机制（指数退避 + rate limit / timeout 重试）

**可选功能**：
- 多模型支持（目前支持通过 provider 默认映射或初始化时自定义 `model_map`）
- 高级缓存策略
- Token计数

**验收标准**：
- [x] 能调用LLM生成文本
- [x] 相同 `cache_key` 返回缓存
- [x] 失败自动重试
- [x] 记录 token usage 元数据
- [x] 有单元测试覆盖 client / provider

**实现亮点**：
- provider 层与 client 层解耦，后续接 `P2.3` 时只需要注入 prompt 和 cache key
- 直接基于 HTTP API 实现，不依赖额外 SDK，保持依赖面最小
- 文件缓存落在 `data/cache/llm/`，便于回放和排查
- OpenAI / Anthropic 的错误处理统一归一到 retryable / non-retryable 语义
- 已完成一次 Anthropic-compatible 第三方网关 live 验证（`/api/v1/messages` + 模型 env 覆盖）

**已知问题**：
- Anthropic-compatible 路径已做真实凭证验证，OpenAI provider 仍未做 live 验证
- 暂未实现 TTL、缓存失效策略和成本统计聚合报表

### P2.3 Enrichment Pipeline ✅ 已完成（2026-03-11）
**依赖**：P0.1, P2.2
**核心功能**：
- ✅ EnrichmentPipeline（读取数据库中的 active artifact）
- ✅ 生成 L1 摘要（一句话）
- ✅ 提取关键词标签并写回 `Artifact.tags`
- ✅ 单次 LLM 调用同时返回 `summary_l1 + tags`
- ✅ 只处理未增强 artifact，已存在摘要和 tags 的内容自动跳过

**可选功能**：
- L2摘要（三段式）
- L3摘要（详细分析）- Phase 2
- 批处理优化

**验收标准**：
- [x] 未增强 Artifact 可生成 `summary_l1`
- [x] 可生成 tags / keywords
- [x] 单次调用完成两个字段，Phase 1 成本可控
- [x] 单元测试覆盖成功、跳过、定向处理、单条失败继续

**实现亮点**：
- 沿用 P2.2 的 `LLMClient`，使用 FAST tier，并为每个 artifact 设置稳定 cache key
- 单条 artifact 失败不会中断整批 enrichment，符合 pipeline 的容错要求
- prompt 模板已落到 `prompts/summarize_artifact.md`，后续可单独迭代 prompt 而不改代码
- 支持把最新 active profile 的兴趣上下文拼入 prompt，便于后续向 relevance / personalization 过渡
- 已完成一次 1168 条 artifact 的 live enrichment，补跑时通过 cache hit 修复单条失败样本

**已知问题**：
- 当前仍是逐条调用，没有做真正的 batch prompt 合并
- 结构化输出仍依赖模型大体遵守 JSON；已新增 relaxed parser 兼容 bare quote / fenced JSON，但更复杂漂移仍可能失败

---

## Priority 3: 评分（核心流程第三步）

### P3.1 Scoring Engine ✅ 已完成（2026-03-10）
**依赖**：P0.1
**核心功能**：
- ✅ BaseScoringStrategy基类（接口定义见15_implementation_guide.md）
- ✅ RecencyStrategy（时效性评分）
  - 按source_tier区分衰减曲线（详见07_scoring_strategy.md 2.2-2.6节）
  - top-tier论文：近1年1.0，1-2年0.95，2-3年0.90，3-5年0.80，5年+0.60
  - 博客：近1月1.0，1-3月0.95，3-6月0.90，6-12月0.80，1年+0.60
  - 基于published_at计算，缺失时用fetched_at或year降级
- ✅ AuthorityStrategy（来源权威性评分）
  - 基于source_tier和source_name（详见07_scoring_strategy.md 3.1-3.2节）
  - top-tier会议：1.0
  - 高质量博客：0.7
  - 其他：0.5
- ✅ CompositeStrategy（组合评分）
  - Phase 1公式：final_score = recency × 0.5 + authority × 0.5
  - 注意：暂不包含relevance（需要LLM），权重调整为各50%
- ✅ 评分结果写入Artifact的score字段和score_breakdown
- ✅ ScoringEngine支持对数据库中已有artifact批量评分

**可选功能（Phase 2+）**：
- RelevanceStrategy ✅ 已在 P7.1 实现
- FeedbackMultiplier（需要反馈数据）
- 多策略实验框架

**验收标准**：
- [x] 每个Artifact有recency_score、authority_score、final_score
- [x] score_breakdown记录各策略的得分
- [x] top-tier近年论文排在前面
- [x] 博客评分低于同期顶会论文
- [x] 可以对数据库中已有的artifact批量评分
- [x] 有单元测试

**实现亮点**：
- 策略层与批处理引擎分离，便于后续插入 RelevanceStrategy
- RecencyStrategy 已覆盖 top-tier / blog / arXiv / advisory 的不同衰减曲线
- CompositeStrategy 固化 Phase 1 公式并把权重写入 `score_breakdown`
- 全量测试通过（28 passed）

**已知问题**：
- relevance_score 已通过 P7.1 启用，keyword match 提供基础区分度，LLM relevance 待 P7.2
- 只有 `year` 没有精确日期的 artifact，recency 只能做粗粒度回退

---

## Priority 4: 报告生成（核心流程第四步）

### P4.1 Report Generator ✅ 已完成（2026-03-10）
**依赖**：P0.1, P3.1
**核心功能**：
- ✅ BaseReportGenerator 抽象基类
- ✅ DailyReportGenerator（日级 UTC 窗口，score < 0.6 自动过滤）
- ✅ WeeklyReportGenerator（ISO week 窗口，Top 10 + score distribution）
- ✅ 纯函数 markdown renderer helpers
- ✅ ArtifactRepository 日期范围查询（`created_at` + `final_score`）
- ✅ 自动写入 `data/reports/daily/` 和 `data/reports/weekly/`
- ✅ 单元测试与集成测试

**可选功能**：
- MonthlyReport
- 候选方向生成（可以Phase 1简化为"Top 3主题"）

**验收标准**：
- [x] 能生成markdown报告
- [x] 周报包含Top 10 artifacts
- [x] 日报/周报在无数据时仍生成空报告
- [x] 格式清晰易读
- [x] 有测试覆盖 renderer / daily / weekly / repository query

**实现亮点**：
- Daily/Weekly 生成器共享基类，日期窗口、缺分告警和写盘逻辑统一
- renderer 保持纯函数，Markdown 输出可单测，不依赖数据库
- 周报同时输出 summary、content breakdown、Top 10、score distribution、按来源汇总列表
- 日报严格区分 high-value / medium-value，只有高分内容显示摘要
- 全量测试通过（47 passed）

**已知问题**：
- 当前报告时间窗口按 `created_at` 过滤，增量重处理的 update-only artifact 不会重新进入报告
- 日报日期参数按 UTC 日历日解释；live 数据全部落在 `2026-03-10` UTC，所以 `2026-03-11` 日报为空
- 仍未包含主题聚类、候选研究方向和行动项（依赖后续 LLM / feedback 能力）

---

## Priority 5: 反馈系统（核心流程第五步）

### P5.1 Feedback Collector ✅ 已完成（2026-03-11）
**依赖**：P0.1
**核心功能**：
- ✅ FeedbackCollector 服务
- ✅ `feedback` CLI 命令收集 artifact 级反馈
- ✅ 保存 append-only `FeedbackEvent` 到数据库
- ✅ 支持 `like / dislike / note`

**可选功能**：
- ProfileUpdater（自动学习偏好）- 可以Phase 1手动更新Profile
- 复杂的偏好建模 - Phase 2

**验收标准**：
- [x] 能对 artifact 提供反馈
- [x] 反馈保存到数据库
- [x] `note` 类型校验 `--note`
- [x] 同一 artifact 的多次反馈 append-only 持久化

**实现亮点**：
- feedback 业务逻辑从 CLI 中拆到 `src/feedback/collector.py`，后续可复用到 UI 或自动化
- 反馈内容统一存成 `{"type": ..., "note": ...}` 结构，便于后续 profile 学习
- CLI 测试覆盖 like / dislike / note / invalid artifact / append-only 行为

**已知问题**：
- 当前只支持 artifact 级反馈，theme / direction 反馈仍 deferred
- Phase 1 收集的反馈不影响评分，feedback multiplier 仍在 Phase 2

---

## Priority 6: CLI和自动化（让系统可用）

### P6.1 CLI工具 ✅ 已完成（2026-03-11）
**依赖**：P1-P5
**核心功能**：
- ✅ `crawl` 命令：运行 paper / blog crawlers
- ✅ `normalize` 命令：处理 raw JSON
- ✅ `enrich` 命令：生成摘要和 tags
- ✅ `score` 命令：批量评分
- ✅ `report` 命令：生成 daily / weekly 报告
- ✅ `feedback` 命令：收集反馈
- ✅ `run` 命令：串联 normalize → enrich → score → report

**可选功能**：
- 更多子命令
- 交互式CLI

**验收标准**：
- [x] 能通过 CLI 运行完整流程
- [x] 命令有帮助文档
- [x] 支持 `python -m src.cli` / `python -m src.cli.main`
- [x] 有 CLI 集成测试

**实现亮点**：
- 顶层 CLI 支持 `--database-url` 和 `--verbose`，便于测试隔离和本地调试
- `run` 命令直接复用现有 normalize / enrich / score / report 模块，没有新增 orchestration 状态
- `click.testing.CliRunner` 覆盖了 report、feedback、run 三条关键路径

**已知问题**：
- `crawl` 命令仍依赖 live 网络和站点稳定性，当前只通过现有 parser 测试保证解析逻辑
- `run` 命令在真实环境中仍依赖有效 LLM 凭证和网络；测试里使用 mock LLM 替代

### P6.2 调度器（可选）
**依赖**：P6.1
**核心功能**：
- 定时运行crawl（每天）
- 定时运行process（每天）
- 定时生成report（每周）

**可选功能**：
- 复杂的调度策略
- 监控和告警

**验收标准**：
- 系统能自动运行
- 有日志记录

---

## Priority 7: 个性化评分（核心流程增强）

### P7.1 Relevance Scoring (Keyword Match) ✅ 已完成（2026-03-11）
**依赖**：P0.1, P3.1
**核心功能**：
- ✅ RelevanceStrategy（基于 Profile preferred_topics / avoided_topics 做 keyword match）
- ✅ 搜索范围覆盖 title + abstract + summary_l1 + tags
- ✅ 命中 1→0.4, 2→0.6, 3→0.8, 4+→1.0, 无命中→0.1
- ✅ avoided_topic 命中时乘 0.3 惩罚系数
- ✅ CompositeStrategy 更新为三因子：recency×0.4 + authority×0.3 + relevance×0.3
- ✅ Profile seed CLI（profile seed / profile show）
- ✅ seed_profile.json 初始用户画像

**验收标准**：
- [x] profile=None 时 relevance 返回 0.5（中性）
- [x] keyword match 在 live 数据上产生 6 档区分度（0.03–0.6）
- [x] final_score 从全部 1.0 分散为 18 档（0.629–0.88）
- [x] High-value 条目从 1168 降到 103
- [x] Top 10 全部是 fuzzing/vulnerability detection 相关论文
- [x] 全量测试通过（82 passed）

**实现亮点**：
- 预留 _calculate_llm_relevance_score 和 _merge_relevance_scores 接口，LLM relevance 可无缝接入
- keyword match 纯本地计算，无 LLM 成本
- avoided_topics 惩罚系数有效将 blockchain 相关论文推到底部

**已知问题**：
- keyword match 无法区分语义近似但领域不同的内容（如 web fuzzing vs binary fuzzing vs sensor fuzzing）
- relevance 最高只到 0.6（命中 2 个 topic），同一年同领域论文仍缺乏细粒度区分
- 需要 LLM relevance scoring 才能真正理解论文与用户兴趣的匹配度

### P7.2 LLM Relevance Scoring ✅ 已完成（2026-03-12）
**依赖**：P7.1, P2.2
**核心功能**：
- ✅ LLMRelevancePipeline 预计算 LLM relevance 分数，存入 score_breakdown
- ✅ prompt v2：精确区分 web fuzzing vs 通用 fuzzing vs 二进制分析
- ✅ 1-5 分映射为 0.0-1.0，与 keyword match 按 0.4/0.6 加权合并
- ✅ 文件缓存 + relevance_version 版本幂等（v1→v2 自动重评）
- ✅ ThreadPoolExecutor 并行（默认 8 workers）
- ✅ CLI: `llm-relevance --provider --workers` + `run` 命令集成

**验收结果**：
- 4116 条 artifact 全部有 llm_relevance_score
- LLM relevance 分布：0.2=2538, 0.4=1131, 0.6=203, 0.8=200, 1.0=44
- final_score 59 档（0.63-0.98），中位数 0.748
- Top 10 以 web 安全直接相关论文为主

**已知问题**：
- CCS 无 abstract（DBLP 不提供），需后续补 ACM DL 抓取
- S&P 无独立论文详情页，abstract 需从 IEEE Xplore 获取

### 爬虫增强：abstract 抓取 ✅ 已完成（2026-03-13）
- NDSS 详情页抓取 abstract：794/794 (100%)
- USENIX Security 详情页抓取 abstract：1550/1556 (99.6%)，CSS selector 修复后重爬完成
- S&P 和 CCS 暂不支持（S&P 无独立论文页，CCS 的 DBLP 无 abstract）
- 当前 abstract 覆盖：2344/3925 (60%)
- LLM relevance 已升级到 v3（利用 abstract 重评全量 3925 条）

### CCS 非 full-paper 过滤 ✅ 已完成（2026-03-12）
- 爬虫层正则过滤 workshop/poster/demo/tutorial/keynote/panel
- cleanup-ccs CLI 命令清理已入库的 191 条历史数据
- SoK 论文不被过滤

### 并行加速 ✅ 已完成（2026-03-12）
- enrichment + llm-relevance 均支持 ThreadPoolExecutor
- CLI --workers 参数，默认 8
- 每个 worker 独立 DB session，线程安全

### P4.2 报告改版 ✅ 已完成（2026-03-12），P4.3 报告重设计 ✅ 已完成（2026-03-13）

**P4.2 核心功能**：
- ✅ 周报 Top 30 + Relevance Distribution + 删全量列表
- ✅ 日报砍掉 medium value 明细
- ✅ `format_score` 增加 relevance 显示

**P4.3 报告重设计**（基于用户消费习惯重新定义日报/周报定位）：
- ✅ 日报 = 博客推荐（近 3 天未读，最多 5 篇）+ 论文动态提示（仅状态机更新时）
- ✅ 周报 = 论文推荐阅读（全库未读 high-relevance，最多 10 篇）+ 博客回顾表格
- ✅ 已读过滤：FeedbackType.READ 标记后报告不再推荐
- ✅ 不同内容类型分栏，不混排
- 设计文档：docs/design/04_report_spec.md

### USENIX abstract 爬虫修复 + 重爬 ✅ 已完成（2026-03-13）
- CSS selector 修复：`div.field--name-...`（双横线）→ `div.field-name-...`（单横线）
- 重爬完成：1550/1556 有 abstract (99.6%)
- LLM relevance v3 全量重评完成（3925 条）
- JSON 解析容错增强（_extract_json_payload）

---

## Phase 1 最小可用版本（MVP）

**必须完成**：P0.1, P1.1, P2.1, P2.2, P2.3, P3.1, P4.1, P5.1, P6.1, P7.1

**可以跳过**：
- Theme模型和主题提取（可以用关键词代替）
- CandidateDirection复杂逻辑（可以简化为Top 3主题）
- DailyReport（只要WeeklyReport）
- 调度器（可以手动运行）
- LLM Relevance Scoring（P7.2，可先只用 keyword match）

**预估时间**：
- 有coding agent：1-2周
- 无coding agent：2-3周

**验收标准**：
1. 能爬取NDSS和S&P论文
2. 能生成摘要和基础个性化评分（含 keyword match relevance）
3. 能生成周报（Top 10论文）
4. 能收集反馈
5. 系统能手动运行完整流程

---

## Phase 2 持续运行能力

**已完成**：
- P7.2 LLM Relevance Scoring ✅
- P4.2 报告改版 ✅
- USENIX abstract 重爬 + v3 relevance ✅

**进行中 / 近期计划**：

### Phase 2a：博客源 live 验证 ✅ 已完成（2026-03-13）
1. ✅ 逐个 live 验证 3 个已有博客爬虫（PortSwigger、Project Zero、Cloudflare）
2. ✅ 修复 HTML selector 漂移问题（Project Zero blogspot → projectzero.google）
3. ✅ 博客数据走完全流程：crawl → normalize → enrich → llm-relevance → score → report
4. ✅ 55 条博客入库

### Phase 2b：GitHub Advisory 爬虫 ⬜（降低优先级）
1. 实现 GitHub Advisory 爬虫（GraphQL API）
2. 接入 normalize pipeline
3. authority 打分暂用 CVSS 映射

> **优先级调整**：Advisory 偏漏洞运营层面，对博士研究选题收敛的直接价值有限。优先实施 Phase 3 智能分析层。

### Phase 2c：调度器 ⬜（降低优先级）
在智能分析层就绪后实现。详见 `docs/design/05_source_plan.md` 第 6 节。

### Phase 2 遗留数据质量问题 ⬜
- S&P 2022-2024 TLS 问题排查（abstract 0/374）
- CCS abstract 从 ACM DL 补抓（abstract 0/1201）

---

## Phase 3 智能分析层（v2 双轨架构）

> **v2 架构转向 (2026-03-16)**：从单一 LLM 分析链重构为双轨处理 + 空白检测。
> 核心变化：Profile 放宽、arXiv 接入、学术/工业分轨、统计空白检测。
> 完整设计：`docs/design/09_intelligence_layer.md`

### P3a：L2 深度分析 ✅ 已完成
- DeepAnalysisPipeline（学术轨，论文 L2 结构化分析）

### P3b：主题聚类 ✅ 已完成
- Theme 模型 + ClusteringPipeline（学术轨，论文聚类）

### Phase A：基础改造 ✅ 已完成（2026-03-16）

**A1: SourceTier 正式化 + 数据迁移** ✅
- SourceTier / InformationTrack / DirectionStatus 枚举
- 分轨评分 CompositeStrategy（学术轨 0.5/0.3/0.2，工业轨 0.5/0.4/0.1）
- `migrate-tiers` CLI 命令
- authority / recency 策略更新

**A2: Profile V2 + 宽泛相关度** ✅
- seed_profile_v2.json（preferred_topics 清空，新增 domain_scope / direction_preferences）
- relevance_score_v4.md（宽泛领域过滤 prompt）
- RelevanceStrategy 处理空 preferred_topics（跳过 keyword match，纯 LLM）
- LLMRelevancePipeline bump v4，自动选择 v4 prompt
- `profile seed-v2` CLI 命令

**A3: arXiv 爬虫** ✅
- ArxivCrawler（cs.CR + cs.SE + cs.PL，Atom XML API）
- 分页、3 秒 rate limit、年份过滤
- 注册到 registry

### Phase B：工业信号轨道 ✅ 已完成（2026-03-16）

**B1: 需求信号提取** ✅
- SignalExtractionPipeline（博客 → 结构化需求信号 JSON）
- prompts/extract_demand_signal.md
- CLI `extract-signals`

**B2: 分轨路由** ✅
- TrackRouter（split_by_track 按 source_tier 分流）
- CompositeStrategy 已在 A1 实现分轨权重

### Phase C：空白检测（核心产出）✅ 已完成（2026-03-16）

**C1: 空白检测** ✅
- ResearchGap 模型 + ResearchGapRepository
- GapDetectionPipeline（统计交叉比对学术覆盖 vs 工业需求）
- CLI `detect-gaps`

**C2: 方向综合** ✅
- CandidateDirection 模型 + CandidateDirectionRepository
- DirectionSynthesisPipeline（基于 ResearchGap + Profile.direction_preferences）
- prompts/synthesize_from_gaps.md
- CLI `synthesize`

**C3: Landscape 报告** ✅
- LandscapeReportGenerator（含空白分析 section）
- `run --full` 串联完整分析链
- `report --type landscape` CLI

### Phase D：趋势 + 反馈

**D1: 统计趋势分析** ✅ 已完成（2026-03-16）
- TrendAnalysisPipeline（定量 trend_direction + 可选 LLM 定性分析）
- prompts/analyze_theme_trend.md
- CLI `trend`，集成到 `run --full`

**D2: 反馈闭环** ⬜
- ProfileSignalPipeline（从反馈历史提取偏好模式，更新 Profile）

---

## 优先级排序（2026-03-16 最终更新）

**已完成**：Phase A + B + C + D1（v2 双轨架构全部实现）

**待做**：
1. **live 验证**：`migrate-tiers` → `profile seed-v2` → `run --full --provider anthropic`
2. **D2 反馈闭环**：ProfileSignalPipeline
3. **Phase 2 数据质量**（S&P TLS、CCS abstract）
4. **T4 源接入**：用户后续提供个人博客/公众号 URL

**当前测试**: 159 passed, 5 subtests passed

---

## P0.1 完成总结（2026-03-09）

**已实现**：
- ✅ 数据模型层完整实现
- ✅ Repository层完整实现  
- ✅ 测试全部通过（6 passed）

**下一步**：
- P1.1 爬虫整合（需补充CCS, USENIX Security + 3个博客爬虫）

**注意**：P1.1是必须完成的，不能跳过。系统需要完整的数据源支持。

---

## P1.1 完成总结（2026-03-09）

**已实现**：
- ✅ BaseCrawler基类和工具函数
- ✅ 四大顶会爬虫完整实现
- ✅ 3个博客爬虫完整实现
- ✅ 爬虫注册机制
- ✅ 测试全部通过（10 passed）

**下一步**：
- P2.1 Normalization Pipeline（将爬虫数据转换为Artifact）

**注意**：P2.1依赖P0.1和P1.1，现在可以开始实现。
