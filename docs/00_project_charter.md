# Project Charter

## 1. Project Name

Research Radar

## 2. Project Goal

构建一个面向安全领域博士研究选题的长期运行系统，围绕未来 3–5 年可能成立的研究方向，持续收集、整理、筛选和收敛多源信号，并通过用户反馈逐步学习偏好，最终辅助研究主线决策。

## 3. Primary User

单人用户，即项目创建者本人。

用户特征：

- 目标是辅助博士研究选题，而不是通用资讯摘要
- 接受系统长期运行
- 接受频繁修改规则和不断迭代
- 愿意为候选方向提供 pros / cons / unknown 等深反馈
- 不需要网页界面
- 重视中间产物和可追溯性

## 4. Problem Statement

当前缺少一个真正围绕“研究方向收敛”而非“内容聚合”来设计的系统。

已有信息获取方式存在以下问题：

- 信息源多而散
- 不同来源之间难以统一比较
- 很难从单条内容上升到长期研究方向
- 缺少可追溯的证据链
- 缺少基于个人判断和长期反馈的方向收敛机制
- 当规则变化后，旧结果难以复现和比较

## 5. Desired Outcome

系统每周产出 3 个候选研究方向。每个方向应当：

- 具有清晰的问题表述
- 有明确论文证据
- 有现实世界信号支持
- 包含值得继续做与不值得做的理由
- 包含关键未知问题
- 包含下一步最小行动建议

随着时间推移，系统应当能够更贴近用户的研究判断和偏好。

## 6. Core Inputs

核心输入优先级如下：

### Tier 1: Academic Sources
- 四大安全会议论文
- 其他重要安全论文
- 与安全相关的重要 research paper

### Tier 2: Real-world Signals
- 前沿安全博客
- 漏洞报告
- 技术通告 / advisory
- 攻防实践相关 write-up

### Tier 3: Personal Signals
- 个人收藏链接
- 后续扩展平台
- 手动加入的候选内容

## 7. Core Outputs

### Daily Radar
简要记录新增的重要内容和小观察。

### Weekly Shortlist
每周输出 3 个 candidate directions。

### Monthly Convergence
汇总月度 continue / watch / drop，并解释变化原因。

## 8. Success Criteria

首版成功标准：

1. 系统能连续运行至少两周
2. 每周稳定输出 3 个候选方向
3. 每个方向具有最小证据链
4. 用户愿意对 3 个方向写 pros / cons / unknown
5. 下一轮结果会受到反馈影响
6. 改规则后可以 replay，并比较新旧差异

## 9. Constraints

- 输出应为中英混合，保留关键英文术语
- 首版不做 Web UI
- 首版优先支持 CLI + Markdown
- 首版应尽量避免复杂框架依赖
- 首版应优先保证可重跑、可追溯和可迭代

## 10. Design Principles

1. 研究方向优先于单条内容
2. 证据链优先于印象判断
3. 中间产物优先于一次性结果
4. 反馈闭环优先于静态推荐
5. 轻架构优先于重平台