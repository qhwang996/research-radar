# CODEX_BACKLOG

> 这是面向 Codex 的连续开发队列。
> 默认一次只做一张票；做完必须更新 `docs/CURRENT_STATUS.md` 和本文件。
> 如果任务与本文件冲突，以本文件的任务定义为准，再回写其它文档。

## 使用规则

- 状态只允许：`todo` / `in_progress` / `blocked` / `done`
- 每张票必须写明依赖、涉及模块、验收标准
- 一次只做一张票
- 若需要人工 review，PR 标题加 `[Needs human review]`
- 先做文档与 triage，再做 source expansion
- 每完成一张票，必须同步更新：
  - `docs/CURRENT_STATUS.md`
  - `docs/CODEX_BACKLOG.md`
  - 以及被行为变化影响到的 policy / runbook / README

## 票据总览

| ID | 标题 | 状态 | 依赖 | Review |
|---|---|---|---|---|
| RR-001 | 仓库重定位与单一文档入口 | done | - | Codex can do directly |
| RR-002 | 多层摘要与 delegate briefing 落位 | todo | RR-001 | Needs human review before merge |
| RR-003 | Triage 引擎与 bucket 分类 | todo | RR-001, RR-002 | Needs human review before merge |
| RR-004 | 日报重构为分层消费视图 | todo | RR-003 | Needs human review before merge |
| RR-005 | 周报与 landscape 收敛 | todo | RR-003 | Needs human review before merge |
| RR-006 | 月报与季报生成器 | todo | RR-005 | Needs human review before merge |
| RR-007 | Feedback 回流与 delegate usefulness 记录 | todo | RR-003 | Needs human review before merge |
| RR-008 | Advisory 作为独立 industry feed 接入 | todo | RR-003 | Needs human review before merge |
| RR-009 | 自动化调度脚本与健康检查 | todo | RR-004, RR-005 | Needs human review before merge |
| RR-010 | Source expansion phase 2（额外博客 / T4 / 可选 SE 轨） | todo | RR-008 | Needs human review before merge |

---

## RR-001 仓库重定位与单一文档入口
**Why now**  
当前最大问题不是缺模块，而是文档入口不统一、定位仍偏旧、README / iteration_plan / handoff 存在漂移。

**Involved files**
- `README.md`
- `AGENTS.md`
- `docs/CURRENT_STATUS.md`
- `docs/PRODUCT_BRIEF.md`
- `docs/TARGET_SYSTEM.md`
- `docs/TRIAGE_POLICY.md`
- `docs/REPORT_POLICY.md`
- `docs/RUNBOOK.md`
- `docs/SOURCE_EXPANSION_PLAN.md`
- `.github/pull_request_template.md`

**Do**
1. 建立 `CURRENT_STATUS.md` 作为唯一入口
2. 明确新定位
3. 保留“研究方向发现”但上移层级
4. 给出后续 backlog 基线
5. 让 README 指向 CURRENT_STATUS

**Done when**
- 新文档落库
- README 定位改写
- iteration_plan 被标记为历史/工程记录而非唯一入口
- PR template 强制要求更新文档

**Completed (2026-04-09)**  
- `README.md` 已改写为新定位，并明确 `CURRENT_STATUS` 为唯一入口。
- `docs/iteration_plan.md` 已改成历史/工程记录，不再作为当前优先级入口。
- `.github/pull_request_template.md` 已新增，强制按统一模板填写目标、测试、回滚和文档更新。
- rewrite notes 与明显无用文件已清理，文档集合进一步收敛。

**Review**  
Codex can do directly

---

## RR-002 多层摘要与 delegate briefing 落位
**Why now**  
没有稳定的多层摘要，就无法做 triage，也无法支持 detailed / delegate 两个消费层。

**Involved files**
- `prompts/summarize_artifact.md`
- `src/pipelines/enrichment.py`
- `src/pipelines/deep_analysis.py`（若需要明确与 `summary_l2` 的职责边界）
- `tests/` 相关 enrichment / pipeline tests
- `docs/TARGET_SYSTEM.md`
- `docs/TRIAGE_POLICY.md`

**Do**
1. 明确 `summary_l1 / summary_l2 / summary_l3` 各自职责
2. 让 `summary_l3` 开始承载 detailed brief / delegate brief
3. 保持 `summary_l2` 继续作为结构化 deep analysis
4. 增加解析与测试覆盖
5. 记录 versioning / fallback 规则

**Done when**
- 生成链路不会覆盖 `summary_l2` 的现有语义
- `summary_l3` 有可测试的生成行为
- triage 所需摘要层级可以直接被 report 使用

**Review**  
Needs human review before merge

---

## RR-003 Triage 引擎与 bucket 分类
**Why now**  
没有 triage，引擎只能“算分”，还不能“减少用户注意力成本”。

**Involved files**
- `src/reporting/`（新增 `triage.py` 或等效模块）
- `src/repositories/` 查询辅助（如需要）
- `tests/` triage / report tests
- `docs/TRIAGE_POLICY.md`
- `docs/CURRENT_STATUS.md`

**Do**
1. 先按 track 分流
2. 再派生五类 bucket
3. 接入 read / dislike 等反馈
4. 让同一 artifact 在一个周期只进一个 bucket
5. 把规则写死在 policy + tests 里，而不是口头约定

**Done when**
- `read_original / detailed_summary / one_line / delegate / archive` 可稳定复现
- academic / industry 不混排
- 报表层能直接调用 triage 结果

**Review**  
Needs human review before merge

---

## RR-004 日报重构为分层消费视图
**Why now**  
当前日报主要还是博客推荐，不足以承接“低管理成本”的真实日常使用场景。

**Involved files**
- `src/reporting/daily.py`
- `src/reporting/renderer.py`（如需要）
- `tests/` daily report tests
- `docs/REPORT_POLICY.md`
- `docs/RUNBOOK.md`

**Do**
1. 改成 academic / industry 分区
2. 每个分区内做 triage buckets
3. 保留 advisories 占位
4. 增加 delegate section
5. 保持空 section 可读

**Done when**
- 日报不再只是博客列表
- academic / industry / advisories 结构明确
- 用户可以直接知道“今天该做什么”

**Review**  
Needs human review before merge

---

## RR-005 周报与 landscape 收敛
**Why now**  
weekly 与 landscape 的语义漂移会持续制造维护成本。

**Involved files**
- `src/reporting/weekly.py`
- `src/reporting/landscape.py`
- `src/cli/report.py`
- `src/cli/process.py`
- `tests/` weekly / landscape / cli tests
- `docs/REPORT_POLICY.md`
- `README.md`

**Do**
1. 定义 weekly 为主周报
2. 给 landscape 一个兼容期定位
3. 共享 triage / section policy
4. 明确 CLI 行为
5. 保持向后兼容

**Done when**
- weekly / landscape 不再各自漂移
- 文档、CLI、输出文件命名至少在语义上统一
- 有清晰兼容说明

**Review**  
Needs human review before merge

---

## RR-006 月报与季报生成器
**Why now**  
用户需求已经明确包含月报与季度总结；没有正式 generator，就只能临时拼接。

**Involved files**
- `src/reporting/` 新 generator
- `src/cli/report.py`
- `src/cli/process.py`（若需要）
- `tests/` report / cli tests
- `docs/REPORT_POLICY.md`
- `docs/RUNBOOK.md`

**Do**
1. 增加 monthly generator
2. 增加 quarterly generator
3. 定义输出路径
4. 接入 feedback / source performance / direction changes
5. 补测试与 runbook

**Done when**
- 月报和季报都有稳定 markdown 输出
- 能从 CLI 调起
- 空数据时仍有可读报告

**Review**  
Needs human review before merge

---

## RR-007 Feedback 回流与 delegate usefulness 记录
**Why now**  
feedback 已存在，但还没有真正改变 triage / 阅读推荐。

**Involved files**
- `src/cli/feedback.py`
- `src/feedback/collector.py`
- `src/models/feedback.py`（若只改结构化 content 约定则无需 schema 变更）
- `tests/` feedback tests
- `docs/TRIAGE_POLICY.md`
- `docs/CURRENT_STATUS.md`

**Do**
1. 扩展 feedback 的 target / outcome 语义
2. 增加 delegate useful / useless 的记录约定
3. 让 monthly / quarterly 能消费这些信号
4. 明确哪些反馈只影响 report、哪些将来影响排序

**Done when**
- 已读/喜欢/不喜欢/代读结果都可结构化记录
- 报表里能看到 feedback snapshot
- triage 可以消费最低限度的反馈信号

**Review**  
Needs human review before merge

---

## RR-008 Advisory 作为独立 industry feed 接入
**Why now**  
当前日报已经留了“漏洞速报”占位，下一步最自然的 industry 扩展就是 advisories。

**Involved files**
- `src/crawlers/`
- `src/pipelines/normalization.py`（如需 tier/source 映射）
- `src/scoring/authority.py`
- `src/reporting/daily.py`
- `tests/`
- `docs/SOURCE_EXPANSION_PLAN.md`

**Do**
1. 接入 1 个 advisory source baseline
2. 单独定义 industry 子分区
3. 定义 authority / urgency / dedupe 规则
4. 接入日报 / 周报
5. 保持与 academic 分离

**Done when**
- daily “漏洞速报”不再为空占位
- advisories 不与 academic 混排
- source policy 文档同步

**Review**  
Needs human review before merge

---

## RR-009 自动化调度脚本与健康检查
**Why now**  
用户明确要低维护和自动化；光有 CLI 还不够，需要最小可操作自动化脚手架。

**Involved files**
- `scripts/` 或 `.github/workflows/`
- `docs/RUNBOOK.md`
- `README.md`
- `tests/`（如有脚本层测试）

**Do**
1. 固化 daily / weekly 操作路径
2. 增加最小健康检查
3. 明确失败后的处理方式
4. 保留手动 rerun 路径

**Done when**
- 至少存在稳定的 daily / weekly automation 模板
- runbook 能支持非交互操作
- 失败时知道如何恢复

**Review**  
Needs human review before merge

---

## RR-010 Source expansion phase 2
**Why now**  
只有在 triage 与报表已经稳定后，额外 source 才不会带来纯噪音。

**Involved files**
- `src/crawlers/`
- `docs/SOURCE_EXPANSION_PLAN.md`
- `README.md`
- `docs/CURRENT_STATUS.md`

**Do**
1. 评估额外 curated blogs
2. 在用户提供 URL 后接入 T4 personal sources
3. 评估是否纳入 SE 安全相关会议轨
4. 做 source performance review

**Done when**
- 每个新 source 都通过准入规则
- 没有破坏 no-mix 原则
- 文档同步记录保留/淘汰理由

**Review**  
Needs human review before merge
