# Research Radar

一个面向安全领域博士研究选题的长期收敛系统。

它的目标不是泛化地“帮我看资讯”或“自动想 idea”，而是围绕未来 3–5 年值得投入的安全研究方向，持续收集多源信号、形成候选方向、记录我的判断，并在长期运行中逐步收敛出更值得做的博士主线。

## Core Goal

系统每周输出 3 个候选研究方向，并通过我的反馈（pros / cons / unknown / next action）持续学习我的研究偏好。

## Why this system exists

我需要的不是一个信息聚合器，而是一个“研究方向收敛器”：

- 以高质量安全论文为核心输入
- 以前沿安全博客、漏洞报告、技术通告为现实世界补强
- 以个人收藏和后续平台为个性化补充
- 保留中间产物，支持频繁修改规则、重跑、比较新旧结果
- 帮助我判断哪些方向值得继续投入，哪些只值得观察，哪些应当放弃

## MVP Goal

首版目标：

1. 接收多类输入源（paper / blog / advisory / bookmark）
2. 把输入统一归一化为 artifact
3. 每周生成 3 个 candidate directions
4. 生成 markdown weekly shortlist
5. 记录我的反馈
6. 下一轮排序能体现反馈影响
7. 保留关键中间产物，支持 replay 和 compare

## Non-goals

首版明确不做：

- Web UI
- 多用户支持
- 复杂分布式架构
- 完整知识图谱
- 很重的 agent framework / LangGraph orchestration
- “一次性自动生成完美博士题目”

## Core Output

系统输出分三层：

- Daily Radar：少量新增观察
- Weekly Shortlist：每周 3 个候选方向
- Monthly Convergence：continue / watch / drop 的方向收敛结果

## Core Principles

1. Papers first  
   论文是主轴，尤其是高质量安全论文。

2. Evidence over impressions  
   每个方向必须有证据链，而不是只靠摘要式印象。

3. Preserve intermediates  
   中间产物必须保留，便于重跑、比较和回溯。

4. Idempotent by design  
   长期运行系统必须考虑幂等、去重、恢复和 replay。

5. Weekly convergence, not information overload  
   目标不是给很多内容，而是给很少但值得思考的方向。

## Proposed Repo Layout

```text
research-topic-system/
  README.md
  .env.example

  docs/
    00_project_charter.md
    01_scope_and_non_goals.md
    02_requirements.md
    03_architecture_overview.md
    04_data_flow.md
    05_data_dictionary.md
    06_idempotency_and_replay.md
    07_scoring_strategy.md
    08_report_spec.md
    09_source_plan.md
    10_feedback_spec.md
    11_iteration_plan.md
    12_risks_and_open_questions.md

  schemas/
  samples/
  prompts/
  reports/
  scripts/
  src/