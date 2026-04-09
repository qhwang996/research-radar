# REPORT_POLICY

## 1. 总原则

报告是主产品，而不是附属物。所有 pipeline 最终都要服务报告输出。

报告必须做到：
- 低维护
- 可重跑
- 结构稳定
- 学术 / 工业分开
- 一眼能看出“我该做什么”

## 2. 报告类型

### 2.1 Daily
目标：5–10 分钟。
回答问题：
- 今天有什么值得注意？
- 哪些要亲读？
- 哪些只看一句话？
- 哪些应该 delegate？

### 2.2 Weekly
目标：30–60 分钟。
回答问题：
- 这周 academic frontier 是什么？
- 这周 industry signal 是什么？
- 哪些是跨轨道 gap？
- 下一周读什么？

### 2.3 Monthly
目标：60–90 分钟。
回答问题：
- 哪些趋势稳定存在？
- 哪些 sources 真有用？
- 哪些 delegate 真的节省了时间？
- 哪些候选方向应升级为研究池？

### 2.4 Quarterly
目标：1–2 小时。
回答问题：
- 哪些方向值得进入季度研究路线图？
- 哪些 source 应保留、扩展、淘汰？
- 哪些主题是阶段性噪音，哪些是真正可持续方向？

## 3. 每种报告都必须遵守的结构规则

1. 先 academic，再 industry，最后 cross-track synthesis
2. 每个 track 内再按 triage bucket 分组
3. 不做 academic + industry 混排 Top-N
4. 每个 bucket 都有数量上限
5. 空 section 也要明确输出“暂无”
6. 所有生成文件都是 Markdown
7. 报告优先输出可执行下一步，而不是堆信息

## 4. Daily 报告结构

建议固定结构：

1. Header / meta
2. Academic
   - Must read original
   - Detailed summary
   - One-line watchlist
   - Delegate to agent
3. Industry
   - Must read original
   - Detailed summary
   - One-line watchlist
   - Delegate to agent
4. Advisories（如果未接入则明确占位）
5. Today stats
6. Carry-over notes（可选）

Daily 中不输出完整 candidate directions，只允许：
- “本条已进入本周 gap shortlist”
- “本条已放入 delegate queue”

## 5. Weekly 报告结构

建议固定结构：

1. Header / week meta
2. Academic frontier
3. Industry signals
4. Cross-track gaps
5. Candidate directions shortlist
6. Must-read queue for next week
7. Delegate queue for next week
8. Feedback snapshot
9. Stats

Weekly 是用户主周报。

## 6. Landscape 的兼容策略

在兼容期内：

- `landscape` 仍保留
- 它可以作为：
  - `weekly` 的战略版
  - 或 `weekly` 的兼容别名
- 但不能继续和 `weekly` 各说各话

兼容期建议：
- `weekly`：主周报
- `landscape`：可选的战略附录/兼容输出
- 如果两个文件都生成，必须共享同一 triage / report policy

## 7. Monthly 报告结构

建议固定结构：

1. 本月最重要的 academic themes
2. 本月最重要的 industry pain signals
3. 重复出现的 gaps
4. 候选方向变化（新增 / 上升 / 下降 / 移除）
5. 阅读 ROI
6. delegate ROI
7. source performance
8. 下月建议关注项

## 8. Quarterly 报告结构

建议固定结构：

1. 季度综述
2. 稳定 academic frontiers
3. 稳定 industry demands
4. 持续 gaps
5. 值得进入研究路线图的方向
6. source expansion / pruning proposal
7. profile / triage 调整建议
8. 下一季度执行建议

## 9. 文件命名策略

### 现有兼容
- daily: `data/reports/daily/YYYY-MM-DD.md`
- weekly: `data/reports/weekly/YYYY-WXX.md`
- landscape: 兼容期内不要硬删旧路径

### 目标扩展
- monthly: `data/reports/monthly/YYYY-MM.md`
- quarterly: `data/reports/quarterly/YYYY-QX.md`

如果 landscape 需要与 weekly 共存，建议：
- weekly: `YYYY-WXX.md`
- landscape: `YYYY-WXX-landscape.md`

但在真正改路径之前，必须先做兼容迁移并更新 runbook。

## 10. 数量上限建议

### Daily
- academic must-read: <= 2
- industry must-read: <= 2
- detailed summary total: <= 8
- delegate total: <= 4
- one-line total: <= 12

### Weekly
- must-read total: <= 10
- delegate total: <= 8
- candidate directions shortlist: <= 5

### Monthly
- 核心主题: <= 10
- 候选方向: <= 8

### Quarterly
- 进入路线图的方向: <= 5

## 11. 何时允许空缺

如果没有足够高价值条目，不要为了“看起来完整”硬塞内容。

允许：
- must-read 为空
- delegate 为空
- candidate direction 为空

不允许：
- academic / industry 结构消失
- 没有说明为什么为空
