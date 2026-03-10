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

**可选功能**：
- 复杂去重算法
- 数据验证

**验收标准**：
- ✅ 能处理爬虫输出
- ✅ Artifact 正确存入数据库
- ✅ 去重有效

**实现亮点**：
- 支持历史 raw 数据重放，不需要迁移旧文件
- 兼容论文和博客两类输入
- 真实数据试跑完成：1499 条 raw 记录归一化后落成 1168 条 artifact
- 全量测试通过（19 passed）

**已知问题**：
- 当前去重仍是 MVP 级别，主要依赖 title key，不包含复杂 alias mapping

### P2.2 LLM服务层
**依赖**：无
**核心功能**：
- LLMClient封装（OpenAI或Anthropic）
- 基础缓存（文件缓存）
- 重试机制

**可选功能**：
- 多模型支持
- 高级缓存策略
- Token计数

**验收标准**：
- 能调用LLM生成文本
- 相同输入返回缓存
- 失败自动重试

### P2.3 Enrichment Pipeline
**依赖**：P0.1, P2.2
**核心功能**：
- 生成L1摘要（一句话）
- 提取关键词

**可选功能**：
- L2摘要（三段式）
- L3摘要（详细分析）- Phase 2
- 批处理优化

**验收标准**：
- 每个Artifact有L1摘要
- 有关键词
- LLM成本可控

---

## Priority 3: 评分（核心流程第三步）

### P3.1 Scoring Engine
**依赖**：P0.1
**核心功能**：
- RecencyStrategy（时效性）
- AuthorityStrategy（来源权威性）
- CompositeStrategy（组合评分）

**可选功能**：
- RelevanceStrategy（需要Profile）- 可以Phase 1简化
- 多策略实验框架 - Phase 3

**验收标准**：
- 每个Artifact有final_score
- 评分合理（最近的高分论文排前面）

---

## Priority 4: 报告生成（核心流程第四步）

### P4.1 Report Generator
**依赖**：P0.1, P3.1
**核心功能**：
- WeeklyReport生成器
- 简单的markdown模板
- 输出Top 10 artifacts

**可选功能**：
- DailyReport
- MonthlyReport
- 候选方向生成（可以Phase 1简化为"Top 3主题"）

**验收标准**：
- 能生成markdown报告
- 报告包含Top artifacts
- 格式清晰易读

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
