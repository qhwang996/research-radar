# AGENTS.md

本仓库当前的基线任务不是“单一的研究方向发现器”，而是：

> 面向安全科研的前沿情报收集、分层消费与周期总结系统

“研究方向发现”保留，但它已经降级为周/月/季度层的上层输出，而不是底层系统唯一目的。

## 0. 你的工作边界

你是持续开发代理，不是产品重新发明者。默认原则：

- Markdown-first
- CLI-first
- automation-first
- additive change first
- rerunnable / idempotent first
- no frontend unless backlog 明确要求
- no broad rewrites unless backlog 明确要求

不要为了“更干净的架构”主动推翻现有 CLI、pipeline、reporting、DB 模型和测试。

## 1. 开始任何任务前必须先读

严格按以下顺序阅读，除非任务只涉及一个极小的局部修复：

1. `docs/CURRENT_STATUS.md`
2. `AGENTS.md`
3. `docs/TARGET_SYSTEM.md`
4. `docs/TRIAGE_POLICY.md`
5. `docs/REPORT_POLICY.md`
6. `docs/CODEX_BACKLOG.md`
7. `README.md`
8. `docs/design/01_architecture.md`
9. `docs/design/03_scoring_strategy.md`
10. `docs/design/04_report_spec.md`
11. `docs/design/05_source_plan.md`
12. `docs/design/09_intelligence_layer.md`
13. `docs/handoff_2026-03-12.md`
14. `docs/design/06_llm_strategy.md`
15. `docs/design/07_idempotency.md`

如果这些文档之间有冲突，以 `docs/CURRENT_STATUS.md` 为当前唯一入口；然后在当前 PR 中把冲突文档修正掉，不要放任漂移继续扩大。

## 2. 默认不要动的部分

除非 backlog 工单明确要求，否则不要改这些基础约束：

- `src/cli/main.py` 的顶层命令注册方式
- `src/cli/process.py` 的基础 orchestrator 结构
- `src/pipelines/normalization.py` 的 `canonical_id` / upsert / RawFetch 增量处理语义
- `src/scoring/composite.py` + `src/scoring/engine.py` 的“写回 `final_score + score_breakdown`”模式
- `src/models/enums.py` 中 tier → track 的基线语义
- `src/reporting/base.py` 的共享写盘逻辑
- 现有 `data/reports/` 输出目录结构，除非工单明确要求兼容迁移

## 3. 当前允许优先推进的方向

只优先做以下四类事情：

1. 文档单一入口化：减少“文档说 A、代码是 B”的漂移
2. 分层消费：把内容稳定分成“亲读 / 详细摘要 / 一句话 / delegate / 归档”
3. 周期报告：把周、月、季度报告做成稳定、自动、低维护输出
4. 反馈回流：把已读/喜欢/不喜欢/代读有用性转成可再利用的信号

## 4. 每个任务的执行流程

### 4.1 任务开始前
- 从 `docs/CODEX_BACKLOG.md` 里选择一个工单
- 在 `docs/CURRENT_STATUS.md` 的 Work Log 中写一行“准备处理什么、依据什么假设”
- 明确本次是否涉及：
  - schema 变更
  - scoring / triage 阈值变化
  - 新 source 接入
  - 报告语义变化

### 4.2 实现时
- 每次 PR 只做一个工单，最多允许一个极小的顺手修复
- 保持修改面最小
- 优先复用已有模块而不是新增平行体系
- 新增逻辑必须可重跑
- 如果需要缓存/版本字段，优先沿用现有 `*_version` / `generation_version` 思路
- 如果只需要报表层分流，不要轻易新增数据库列

### 4.3 完成后必须更新
每个任务完成后，至少更新：

- `docs/CURRENT_STATUS.md`
- `docs/CODEX_BACKLOG.md`

视情况还必须更新：

- `docs/RUNBOOK.md`：如果命令、运行方式、失败处理变了
- `docs/TRIAGE_POLICY.md`：如果分层规则变了
- `docs/REPORT_POLICY.md`：如果报告结构/命名/输出变了
- `docs/SOURCE_EXPANSION_PLAN.md`：如果 source 策略变了
- `README.md`：如果外部入口、定位、快速开始变了

## 5. 进度汇报格式

每个 PR 描述和每次阶段性汇报都使用同一模板：

### Goal
这次解决什么问题。

### Why now
为什么这个工单现在做，而不是之后。

### Files changed
列出核心改动文件。

### Behavior changed
用 3–8 条描述实际行为变化，不写空话。

### Tests
写明运行了哪些命令、结果如何。

### Rollback
如果要撤回，最小回退面是什么。

### Docs updated
明确写出更新了哪些文档。

### Risks / Follow-ups
剩余风险和推荐下一个工单。

## 6. 什么时候必须停下并等待人工 review

出现以下任一情况时，不要继续扩张实现，提交当前结果并标记 `Needs human review before merge`：

- 需要数据库 schema 迁移
- 需要新增外部 source
- 需要改 scoring 权重或 triage 阈值
- 需要改变 report 文件命名或目录兼容策略
- 需要用户提供 T4 个人源 URL
- 需要决定某类 source 是否值得长期维护
- 测试失败是由 live 网络 / 第三方站点 / LLM provider 波动引起
- 你发现旧文档和现有实现冲突，但无法确定以谁为准

## 7. 明确禁止

- 不要直接引入前端
- 不要新增一个与现有 CLI 平行的 orchestrator
- 不要把 academic 和 industry 混成一个排行榜
- 不要把“研究方向发现”重新拉回底层唯一目标
- 不要为了解决单个报表需求而破坏重跑/幂等性
- 不要悄悄删除历史路径或兼容命令

## 8. 工程上的默认偏好

- 报表/策略问题，优先在 reporting 层解决
- 多级摘要问题，优先复用 `summary_l1 / summary_l2 / summary_l3`
- delegate 相关的元信息，优先放在 `score_breakdown` 或派生报表逻辑里，避免第一步就加新表
- feedback 先复用 append-only event；不要第一步就做复杂在线学习
- 新报告类型优先沿用 `BaseReportGenerator`
- 如果 weekly 与 landscape 有冲突，先做兼容层，再做收敛，不要硬切

## 9. 成功标准

你的工作成功，不是因为“代码更多了”，而是因为：

- 用户几乎不用盯项目
- 每天有稳定可读输出
- 周/月/季度有清晰分层总结
- Codex 可以连续接下一张票继续做
- 文档比代码更先解释清楚行为
