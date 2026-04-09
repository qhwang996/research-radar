# CURRENT_STATUS

> 这是后续所有 agent / Codex 会话的唯一主入口。
> 如果 README、iteration_plan、旧 handoff 与本文件冲突，以本文件为准，并在当前 PR 中补齐漂移。

## 1. 当前定位

本仓库已经从“安全博士研究方向发现系统”重定位为：

> 面向安全科研的前沿情报收集、分层消费与周期总结系统。

“研究方向发现”保留为上层输出，而不是底层唯一目标。

## 2. 现状总览

### 2.1 已经可用
- crawl / normalize / enrich / llm-relevance / score / report / run CLI 已存在
- academic / industry 双轨概念已在模型、设计文档和若干 pipeline 中落地
- daily / weekly / landscape 报告生成已存在
- gap detection / direction synthesis 已存在
- feedback event 已存在，并支持 append-only 记录
- RawFetch + canonical_id + upsert 已经提供可重跑基础

### 2.2 真正还缺的
- 报告层还没有完成“亲读 / 详细摘要 / 一句话 / delegate / 归档”的稳定分层
- 月报、季报尚未成为正式一等输出
- 反馈还没有真正回流成排序/triage偏好
- advisories 仍未接入
- weekly 与 landscape 的语义和命名仍有漂移
- 文档存在明显时间差与实现差异

## 3. 文档优先级（冲突解决顺序）

1. `docs/CURRENT_STATUS.md`
2. `AGENTS.md`
3. `docs/TARGET_SYSTEM.md`
4. `docs/TRIAGE_POLICY.md`
5. `docs/REPORT_POLICY.md`
6. 代码实现
7. `README.md`
8. `docs/iteration_plan.md`
9. 旧 handoff / 历史设计文档

说明：
- 历史设计文档仍然重要，但不再自动等于“当前行为”
- 如果代码与文档冲突，优先写清楚“当前真实行为”再决定是否改代码

## 4. 当前代码骨架（保持不动的默认基础）

### 4.1 编排层
- 顶层 Click CLI 保持不动
- `run` 仍然是默认 orchestrator
- 不新增第二套平行流程

### 4.2 数据层
- `Artifact` 保留 `summary_l1 / summary_l2 / summary_l3`
- `summary_l2` 目前视为 L2 结构化深度分析承载位
- `score_breakdown` 继续承载衍生评分/轨道元信息
- `FeedbackEvent` 继续 append-only

### 4.3 报告层
- `BaseReportGenerator` 保持
- `daily.py / weekly.py / landscape.py` 在现有基础上演进
- 新周期报告优先沿用同一 reporting 体系

## 5. 当前已确认的“文档-实现漂移”

这些问题不是 bug backlog 的边缘问题，而是当前最高优先级文档债：

### Drift A: 入口与状态数字曾分散在 README / handoff / iteration_plan
- 2026-04-09 已收敛：README 现在只承载定位、入口和稳定使用说明
- 2026-04-09 已收敛：`iteration_plan.md` 现在只承载历史/工程记录
- `handoff_2026-03-12.md` 保留为 dated snapshot，不再作为 current status

处理原则：
- 以后不要在多个地方重复维护“唯一状态”
- 把最新状态集中写到本文件

### Drift B: weekly 与 landscape 的语义不一致
- 部分文档说 landscape 取代了 original weekly
- 代码里 weekly 和 landscape 仍同时存在

处理原则：
- 保留兼容命名
- 先收敛行为，再决定是否废弃某个名字

### Drift C: 评分文档与实现存在历史版本并存
- 2026-04-09 已收敛：`iteration_plan.md` 的旧单一权重表述已降级为历史记录
- 当前实现继续按 track 切权重，并写入 `score_breakdown`

处理原则：
- 不新增 `academic_score` / `industry_score` 列
- 继续沿用 `final_score + score_breakdown.track/weights`

## 6. 当前开发原则

未来连续开发时，默认按以下顺序推进：

1. triage 分层
2. 日/周报重构
3. 月/季报
4. feedback 回流
5. advisories
6. 自动化调度
7. 额外 sources

## 7. 当前明确不建议做的事

- 不要先接大量新源
- 不要先做 UI
- 不要重写 scoring engine
- 不要把 academic / industry 合并成一个队列
- 不要先做复杂 agent orchestration
- 不要先做 schema-heavy 重构

## 8. 下一阶段推荐起手工单

优先连续做这 4 张票：

1. `RR-002` 多层摘要与 delegate briefing 语义落位
2. `RR-003` triage 引擎
3. `RR-004` 日报重构
4. `RR-005` 周报与 landscape 收敛

`RR-001` 已完成。只有上面这 4 张票继续收敛，后面的月/季报与 feedback 回流才会真正稳。

## 9. Assumptions

默认假设：
- 单用户
- 本地 SQLite 持久化继续保留
- CLI 是主入口
- monthly / quarterly 先走 markdown 文件，不做数据库大重构
- T4 个人源只有在用户提供 URL 后才接入
- advisories 在接入前始终作为独立 industry 子类，不与 academic 混排

## 10. Work Log

> 每做完一个工单都更新这里。不要只更新代码。

- 2026-04-09: 准备处理 RR-001 的 iteration_plan 收敛与旧文档清理；假设只删除明确的草稿/垃圾文件，不删除仍有历史参考价值的 dated 文档。
- 2026-04-09: 完成 iteration_plan 历史化改写、PR template 建立、rewrite notes 清理与 `.DS_Store` 删除；RR-001 进入完成状态。
- 2026-04-09: 准备处理 RR-001 的 README 重写；假设 `docs/CURRENT_STATUS.md` 为唯一真值入口，本次不涉及 schema 变更、scoring / triage 阈值变化、新 source 接入或 report 文件兼容策略调整。
- 2026-04-09: 完成 README 重写，使外部入口改为“前沿情报收集 + 分层消费 + 周期总结”，并明确 `CURRENT_STATUS` 为唯一入口；本次仅做文档收敛，不改代码行为。
- 2026-04-09: 建立新的仓库定位、文档入口、triage/report/source/backlog/rules 基线。
