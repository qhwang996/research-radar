# Risks and Open Questions

---

## 技术风险

### R1: LLM成本超预算

**风险**：月度预算 $30-60，实际成本可能超标。

**缓解**：严格缓存（相同内容不重复调用）、Phase 1 只用 FAST tier 生成 L1 摘要、监控 token 消耗。

**状态**：待 live 验证

---

### R2: 爬虫失效

**风险**：网站改版、反爬虫、网络不稳定。

**缓解**：重试机制（3次指数退避）、DBLP fallback (CCS)、博客 parser 已做 live validation。

**已知问题**：
- CCS 官方页面依赖前端加载，已通过 DBLP fallback 缓解
- 博客模板可能漂移，已扩展兼容当前页面结构

**状态**：部分缓解

---

### R3: 数据质量

**已知问题**：
- 部分 artifact 只有 year 没有 published_at，recency 评分精度有限（用年中时间点回退）
- 报告按 created_at 过滤，增量重处理的 update-only artifact 不会出现在新报告中
- 报告日期窗口按 UTC 解释，操作时如果按本地时区理解日期，可能得到空日报
- Raw JSON 历史格式不一致，NormalizationPipeline 已兼容 legacy 和 current 格式
- Raw 文件删除条目时不会自动回收旧 artifact（Phase 1 只做 append/update）
- 当前 live 语料全部是 2025 顶会论文，P3.1 的 recency + authority 在该数据集上区分度很弱，weekly top list 大量并列 1.0

**状态**：Phase 1 接受

---

### R3.1: Enrichment 结构化输出漂移

**风险**：LLM 可能输出非 JSON 格式（Markdown fence、额外解释文字）。

**缓解**：已支持去除 code fence、单条失败不阻塞整批，并新增 relaxed parser 兼容 summary 中 bare quote 导致的 JSON 失效。

**已知问题**：
- 2026-03-11 live run 中，artifact `527` 曾返回 fenced JSON 且 `summary_l1` 内含未转义双引号，首轮 enrichment 因此失败
- 同一条目在补跑时通过 cache hit + relaxed parser 成功恢复，无需再次调用 provider

**状态**：已 live 验证，部分缓解

---

### R4: 系统稳定性

**风险**：长期运行崩溃、数据库损坏、磁盘空间不足。

**缓解**：异常处理、定期备份（待实现）、日志。

**状态**：待实现

---

### R4.1: LLM provider 未真实验证

**风险**：OpenAI/Anthropic 适配器只通过 mock 测试，未用真实 API key 做端到端验证。

**缓解**：live 部署前用低成本模型做 smoke test、配置 API budget cap。

**已知问题**：
- Anthropic-compatible 第三方网关已在 2026-03-11 完成 live 验证，使用完整 endpoint `/api/v1/messages`
- OpenAI-compatible 路径仍未做 live 验证

**状态**：部分缓解

---

### R4.2: CLI `run` 命令在真实环境依赖网络和凭证

**风险**：`run` 会串联 crawl → normalize → enrich → score → report。真实执行时既依赖 crawler 网络访问，也依赖 LLM provider 凭证。

**缓解**：
- 本地开发和测试优先使用 `--skip-crawl`
- CLI 集成测试里对 enrichment 使用 mock LLM
- live 使用前先分别 smoke test `crawl` 和 `enrich`

**状态**：Phase 1 接受

---

## 开放问题

### Q1: 主题提取策略

Phase 1 跳过主题提取，直接推荐 Top 10。Phase 2 再实现主题聚类。

### Q2: 候选方向生成

Phase 1 简化为 Top artifacts 排序。Phase 2 实现 LLM 驱动的方向生成。

### Q3: Profile 更新策略

Phase 1 手动编辑 Profile。Phase 2 实现从反馈自动学习偏好。

### Q4: Feedback → 评分集成

Phase 1 只收集反馈，不影响评分。Phase 2 接入 feedback_multiplier。

---

## 决策记录

### D1: Phase 1 跳过主题提取 (2026-03-09)
直接推荐 Top 10，避免过度工程。

### D2: 使用 SQLite (2026-03-09)
单用户系统，部署简单，后续可迁移。

### D3: Normalization 不调用 LLM (2026-03-10)
LLM 放在 Enrichment 阶段，保持 Normalization 纯数据转换。

### D4: Phase 1 评分只用 recency + authority (2026-03-10)
relevance 需要 LLM，先跑起来再加。

### D5: P5.1 + P6.1 合并 (2026-03-11)
CLI 和 Feedback Collector 合为一个任务，一次交付完整 CLI。

### D6: Phase 1 Feedback 不影响评分 (2026-03-11)
只收集，feedback_multiplier 接入 deferred to Phase 2。
