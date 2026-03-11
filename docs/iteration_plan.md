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

**已知问题**：
- 当前只完成 live API 协议适配和 mocked 测试，尚未用真实 API key 做端到端验证
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

**已知问题**：
- 当前仍是逐条调用，没有做真正的 batch prompt 合并
- 结构化输出依赖模型遵守 JSON 格式，live 环境下仍需 smoke test 验证稳定性

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
- RelevanceStrategy（需要LLM + Profile）
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
- 当前 relevance_score 仍未启用，Phase 1 只依赖 recency + authority
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
- 仍未包含主题聚类、候选研究方向和行动项（依赖后续 LLM / feedback 能力）

---

## Priority 5: 反馈系统（核心流程第五步）

### P5.1 Feedback Collector
**依赖**：P0.1
**核心功能**：
- CLI命令收集反馈
- 保存FeedbackEvent到数据库

**可选功能**：
- ProfileUpdater（自动学习偏好）- 可以Phase 1手动更新Profile
- 复杂的偏好建模 - Phase 2

**验收标准**：
- 能对artifact提供反馈
- 反馈保存到数据库

---

## Priority 6: CLI和自动化（让系统可用）

### P6.1 CLI工具
**依赖**：P1-P5
**核心功能**：
- `crawl` 命令：运行爬虫
- `process` 命令：处理数据（normalize + enrich + score）
- `report` 命令：生成报告
- `feedback` 命令：收集反馈

**可选功能**：
- 更多子命令
- 交互式CLI

**验收标准**：
- 能通过CLI运行完整流程
- 命令有帮助文档

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

## Phase 1 最小可用版本（MVP）

**必须完成**：P0.1, P1.1, P2.1, P2.2, P2.3, P3.1, P4.1, P5.1, P6.1

**可以跳过**：
- Theme模型和主题提取（可以用关键词代替）
- CandidateDirection复杂逻辑（可以简化为Top 3主题）
- DailyReport（只要WeeklyReport）
- 调度器（可以手动运行）
- RelevanceStrategy（可以只用Recency + Authority）

**预估时间**：
- 有coding agent：1-2周
- 无coding agent：2-3周

**验收标准**：
1. 能爬取NDSS和S&P论文
2. 能生成摘要和评分
3. 能生成周报（Top 10论文）
4. 能收集反馈
5. 系统能手动运行完整流程

---

## Phase 2 持续运行能力

**新增模块**：
- Evolution Tracker（追踪热度变化）
- L2/L3摘要生成
- 关联发现
- 调度器（自动运行）

**预估时间**：1-2周

---

## Phase 3 智能优化

**新增模块**：
- 多策略实验框架
- 预测性分析
- 高级主题提取

**预估时间**：持续迭代

---

## 一个月内能完成什么？

### 乐观情况（有coding agent，效率高）
- Week 1: 完成Phase 1 MVP
- Week 2: 试运行，调整参数，修复bug
- Week 3: 完成Phase 2部分功能（演化追踪、调度器）
- Week 4: 持续运行验证，优化

### 保守情况
- Week 1-2: 完成Phase 1 MVP
- Week 3: 试运行，调整
- Week 4: 开始Phase 2

### 建议策略
1. **快速完成MVP**（1周）
2. **立即试运行**（收集真实数据，验证价值）
3. **根据试运行结果决定Phase 2优先级**
4. **不要追求完美，先让系统跑起来**

---

## 提前完成怎么办？

### 如果Phase 1提前完成
1. **立即试运行2周**（这是最重要的）
2. 根据试运行发现的问题优先修复
3. 如果运行顺利，开始Phase 2

### 如果Phase 2提前完成
1. 继续试运行，积累数据
2. 开始Phase 3的策略实验
3. 或者添加更多数据源（CCS, USENIX, arXiv）

### 灵活调整原则
- **价值优先**：优先做对你最有价值的功能
- **数据驱动**：根据试运行结果调整优先级
- **不要过度工程**：够用就好，不要追求完美

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
