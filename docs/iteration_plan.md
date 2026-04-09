# Iteration Plan

> 本文件现在是历史/工程记录，不是当前唯一入口。
> 当前真实状态请先看 `docs/CURRENT_STATUS.md`。
> 当前连续开发队列请看 `docs/CODEX_BACKLOG.md`。
> 如与其它文档冲突，优先级为：`docs/CURRENT_STATUS.md` > `AGENTS.md` > `docs/TARGET_SYSTEM.md` > 本文件。

## 1. 为什么还保留这个文件

保留本文件的目的不再是“告诉你下一步先写数据库还是先写爬虫”，而是：

- 记录仓库已经完成过哪些阶段
- 保留历史验收标准、工程亮点和已知问题
- 帮助后续 agent 理解系统是如何逐步长成现在这个样子的
- 避免每次新会话都把旧阶段重新当作当前优先级

因此，本文件记录的是：

1. 已完成历史阶段
2. 当前收敛阶段
3. 下一阶段 backlog 摘要

## 2. 已完成历史阶段

### H0: 数据基础层

**完成时间**
- 2026-03-09

**已完成内容**
- `Artifact / FeedbackEvent / Profile` 等基础模型
- Repository 层和数据库 session 基础设施
- 基础测试与 CRUD 验收

**保留的历史验收**
- 数据库可创建
- Repository 可独立 CRUD
- 基础模型和异常处理已落库

**保留的工程结论**
- SQLite-first 仍是默认选择
- append-only feedback 仍是默认约束
- 不需要为了当前阶段重新设计数据库基座

### H1: 采集层 baseline

**完成时间**
- 2026-03-09

**已完成内容**
- 四大顶会爬虫
- 3 个研究博客爬虫
- `BaseCrawler`、注册机制、重试与日志
- 统一 raw JSON 输出格式

**保留的历史验收**
- 顶会与博客基线源可独立抓取
- 采集输出为统一 JSON
- 爬虫层有基本错误处理和测试

**保留的已知问题**
- 站点模板漂移始终存在
- CCS / S&P 的部分数据质量缺口需要后续单独处理

### H2: 处理层 baseline

**完成时间**
- 2026-03-10 到 2026-03-12

**已完成内容**
- Normalization pipeline
- `RawFetch + content_hash + normalize_version`
- `canonical_id` 生成与 upsert
- LLM client、缓存、重试
- enrichment（`summary_l1 + tags`）
- LLM relevance 预计算与并行执行

**保留的历史验收**
- raw 文件可安全重放
- 相同内容不会重复污染 artifact
- 增量处理可通过 `RawFetch` 跳过未变化输入
- enrichment / llm-relevance 支持批处理和单条失败隔离

**保留的工程结论**
- `RawFetch + canonical_id + upsert` 是当前可重跑基座
- LLM 输出应优先缓存，不靠隐式内存状态
- 处理链路优先保持幂等，而不是追求一步到位的“完美重构”

### H3: 消费层 baseline

**完成时间**
- 2026-03-10 到 2026-03-13

**已完成内容**
- Scoring engine baseline
- Daily / Weekly report generator baseline
- Feedback collector baseline
- CLI baseline（`crawl / normalize / enrich / score / report / feedback / run`）

**保留的历史验收**
- `final_score + score_breakdown` 已稳定写回
- Daily / Weekly 能产出 Markdown 报告
- feedback 可 append-only 记录
- CLI 可串联完整 baseline 流程

**已降级为历史表述，不再视为当前优先级**
- “weekly 报告是最终主输出”
- “只要 weekly 就够”
- “单一 research direction discovery 是顶层目标”

**当前替代规则**
- 报告语义以 `docs/REPORT_POLICY.md` 为准
- triage 语义以 `docs/TRIAGE_POLICY.md` 为准
- 仓库定位以 `docs/CURRENT_STATUS.md` 为准

### H4: Intelligence Layer v2

**完成时间**
- 2026-03-16

**已完成内容**
- `SourceTier / InformationTrack` 正式化
- `profile seed-v2` 与宽泛相关度过滤
- arXiv crawler
- `deep-analyze`
- `cluster`
- `extract-signals`
- `trend`
- `detect-gaps`
- `synthesize`
- `landscape` 报告与 `run --full`

**保留的历史验收**
- 双轨架构已落到代码，不再是纯设计
- gap detector 和 direction synthesis 已可运行
- academic / industry 在模型、评分和若干 pipeline 中已经分开

**保留的工程结论**
- 这套 intelligence layer 已经存在，不需要再从“Phase A/B/C/D”重新立项
- 当前主要问题不再是“缺一个新 pipeline”，而是 report / triage / feedback 的收敛不够

## 3. 当前收敛阶段

### 3.1 已完成的入口收敛

`RR-001` 已在 2026-04-09 完成：

- `docs/CURRENT_STATUS.md` 成为唯一当前入口
- `README.md` 改为稳定定位页
- 本文件改为历史/工程记录
- `CODEX_BACKLOG` 成为当前连续开发队列

### 3.2 当前最高优先级

这些是当前应该优先连续推进的工作：

1. `RR-002` 多层摘要与 delegate briefing 落位
2. `RR-003` triage 引擎与 bucket 分类
3. `RR-004` 日报重构为分层消费视图
4. `RR-005` weekly / landscape 收敛
5. `RR-006` 月报 / 季报
6. `RR-007` feedback 回流

### 3.3 当前中优先级

- `RR-008` advisories
- `RR-009` 自动化调度
- `RR-010` source expansion phase 2

### 3.4 当前低优先级

- 复杂在线个性化模型
- UI / frontend
- 大规模 source 扩张
- 新开一套平行 orchestrator

## 4. 下一阶段 backlog 摘要

### 4.1 分层消费收敛

目标：
- 让内容稳定进入 `read_original / detailed_summary / one_line / delegate_to_agent / archive`
- 让日报不再只是“列表输出”，而是真正降低注意力管理成本

对应票据：
- `RR-002`
- `RR-003`
- `RR-004`

### 4.2 周期总结收敛

目标：
- 统一 weekly 与 landscape 的语义
- 增加 monthly / quarterly 正式输出
- 让方向发现回到周期总结层，而不是底层唯一目标

对应票据：
- `RR-005`
- `RR-006`

### 4.3 反馈与可维护性

目标：
- 让反馈开始真正影响 triage / report
- 让自动化和 source expansion 建立在稳定报表之上

对应票据：
- `RR-007`
- `RR-008`
- `RR-009`
- `RR-010`

## 5. 历史目标的降级说明

以下说法保留其历史背景，但不再作为当前行为定义：

- “weekly 是最终主输出”
- “landscape 已完全替代 weekly”
- “系统的底层唯一目标是 research direction discovery”
- “单一评分公式就是当前实现”
- “下一步应该回到数据库 / 爬虫 / normalize 的施工顺序”

如果需要当前真实语义：

- 定位看 `docs/CURRENT_STATUS.md`
- triage 看 `docs/TRIAGE_POLICY.md`
- 报告看 `docs/REPORT_POLICY.md`
- source 策略看 `docs/SOURCE_EXPANSION_PLAN.md`
- 目标系统看 `docs/TARGET_SYSTEM.md`

## 6. 仍然保留的历史资料

下面这些文件仍有价值，但它们是历史资料，不是当前入口：

- `docs/handoff_2026-03-12.md`
- `docs/live_run_report_2026-03-11.md`
- `docs/implementation_guide.md`

使用方式：

- 需要看某次会话结论时，读 dated handoff / live report
- 需要看旧接口思路时，读 implementation guide
- 需要决定“现在该做什么”时，不要先看这些文件，先看 `CURRENT_STATUS` 和 `CODEX_BACKLOG`
