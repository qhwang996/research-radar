# Source Plan

## 1. 数据源分层

数据源按权威性和更新频率分为两个维度：

### 1.1 权威性分层（Source Tier）

| Tier | 类型 | 示例 | authority 基线 | 说明 |
|------|------|------|---------------|------|
| T1 | 顶会论文 | NDSS, S&P, CCS, USENIX Security | 1.0 | 经过同行评审，最高权威性 |
| T2 | 知名安全研究博客 | PortSwigger Research, Google Project Zero, Cloudflare | 0.7 | 机构背书，内容质量稳定 |
| T3 | 漏洞公告 | GitHub Advisory, NVD, AVD | 待设计 | 质量参差不齐，需要更精细的打分方案 |
| T4 | 个人/公司博客 | 待筛选 | 待设计 | 质量参差不齐，需要更精细的打分方案 |

**当前实现**：T1 + T2（已有爬虫，T2 尚未 live 验证）
**近期目标**：T2 live 验证 + GitHub Advisory 爬虫（T3 首个源）
**T3/T4 打分方案**：待后续设计，需要比 T1/T2 更精细的 authority 评估维度

### 1.2 更新频率分层

| 频率 | 数据源 | 调度策略 |
|------|--------|----------|
| 低频（月级） | 顶会论文 | 每天轻量状态检测，变化时触发重爬 |
| 高频（日级） | 博客、漏洞公告 | 每天定时爬取 |

---

## 2. Papers (T1)

### 2.1 四大顶会 — 已实现

| 会议 | 会期 | 数据库条数 | abstract 覆盖 |
|------|------|-----------|--------------|
| NDSS | 每年 2-3 月 | 794 | 794/794 (100%) |
| IEEE S&P | 每年 5 月 | 374 | 0/374 |
| ACM CCS | 每年 10-11 月 | 1201 | 0/1201 |
| USENIX Security | 每年 8 月 | 1556 | 1550/1556 (99.6%) |

### 2.2 论文发布状态机

每个顶会的论文按年度经历以下状态：

```
[未公布] → [Cycle1 通知: 标题+作者] → [Cycle2 通知: 标题+作者] → [论文公开: abstract+PDF]
```

各会议 2026 年时间线（月级）：

| 会议 | Cycle 1 通知 | Cycle 2 通知 | 论文公开 |
|------|-------------|-------------|---------|
| S&P 2026 | 2026-03 | — | 2026-05 |
| USENIX 2026 | 2025-12 | 2026-05 | 2026-08 |
| CCS 2026 | 2026-04 | 2026-07 | 2026-11 |
| NDSS 2027 | 2026-07 | 2026-10 | 2027-02 |

**调度策略**：每天对各会议技术议程页做轻量检测（HTTP GET + 页面 hash），内容变化时触发重爬 + normalize + enrich + score。大部分日子不会有变化。

### 2.3 年份范围

**保留 5 年**：当前年份往前 4 年（2022-2026）。超过 5 年的论文对研究选题的参考价值有限。

### 2.4 已知数据缺口

- IEEE S&P 2022-2024：TLS SSLEOFError，需重试或换代理
- CCS：DBLP 不提供 abstract，需后续从 ACM DL 补抓
- IEEE S&P：无独立论文详情页，abstract 需从 IEEE Xplore 或其他渠道获取

### 2.5 软工顶会安全 track — 未实现

- ICSE, FSE, ASE 的 Security track
- 评分已预留 source_tier 支持

### 2.6 arXiv — 未实现

- API: arXiv API，分类 cs.CR
- 评分已预留衰减曲线

---

## 3. Blogs (T2)

### 3.1 已实现爬虫（尚未 live 验证）

| 博客 | URL | 说明 | source_tier |
|------|-----|------|-------------|
| PortSwigger Research | https://portswigger.net/research | Web 安全研究，高度相关 | high-quality-blog |
| Google Project Zero | https://googleprojectzero.blogspot.com/ | 漏洞研究，深度分析 | high-quality-blog |
| Cloudflare Security Blog | https://blog.cloudflare.com/tag/security/ | 安全+基础设施 | high-quality-blog |

**当前状态**：爬虫代码已写，registry 已注册，normalize 已支持 blogs 类型。但从未 live 执行过，需要验证：
1. HTML 结构是否仍然匹配（网站可能已改版）
2. 输出格式是否能正确 normalize
3. authority=0.7 的博客在报告中的排序位置是否合理

### 3.2 潜在新增博客源

| 博客 | URL | 说明 | 优先级 |
|------|-----|------|--------|
| Trail of Bits | https://blog.trailofbits.com/ | 程序分析、fuzzing | 高 |
| Phrack | http://www.phrack.org/ | 经典黑客杂志 | 中 |
| The Daily Swig | https://portswigger.net/daily-swig | 安全新闻 | 中 |

新增博客源需要逐个评估：内容质量、更新频率、与用户兴趣的匹配度。宁缺毋滥。

---

## 4. Advisories (T3) — 未实现

### 4.1 优先候选

| 源 | URL / API | 说明 | 数据量 |
|----|-----------|------|--------|
| GitHub Advisory | https://github.com/advisories (GraphQL API) | 结构化，易于爬取 | ~日均 10-50 |
| NVD | https://services.nvd.nist.gov/rest/json/cves/2.0 | NIST 官方，RESTful API | ~日均 50-100 |
| AVD (阿里) | https://avd.aliyun.com/ | 中文漏洞库 | 待调研 |

### 4.2 Authority 打分方案 — 待设计

漏洞公告的权威性不能简单给一个固定值，需要更精细的维度：
- CVSS 评分（已有预留：`_advisory_score` 方法根据 CVSS 7.0+ → 0.9, 4.0+ → 0.7）
- 是否有 POC / exploit
- 影响范围（vendor 知名度）
- 是否与用户研究方向相关

这块暂不实现，先把 T1+T2 数据质量做扎实。

---

## 5. 个人/公司博客 (T4) — 未实现

质量参差不齐，需要更详细的打分方案才能接入。否则海量低质量数据会稀释报告价值。

可能的评估维度：
- 作者学术背景（h-index、顶会发表记录）
- 博客历史文章质量
- 社区引用/转发量
- 内容与用户兴趣的匹配度

暂不纳入 Phase 2 计划。

---

## 6. 调度策略

### 6.1 日常调度（每天一次）

| 任务 | 数据源 | 做什么 |
|------|--------|--------|
| 博客爬取 | T2 博客（3 个源） | fetch_articles → normalize → enrich → score |
| 论文状态检测 | T1 顶会（4 个源） | 轻量 check 技术议程页是否有变化 |
| 论文重爬（条件触发） | 变化的顶会 | 全量重爬 → normalize → enrich → llm-relevance → score |
| 日报生成 | — | 生成当日 daily report |

### 6.2 周报（每周一次）

- 生成 weekly report

### 6.3 论文状态检测机制

每天对各会议的技术议程页（listing page）做 HTTP GET，计算页面内容 hash，与上次记录对比：
- hash 不变 → 跳过
- hash 变化 → 触发该会议的全量重爬 + 下游 pipeline

存储：在 DB 中记录每个会议 listing page 的 `last_hash` 和 `last_checked_at`。

---

## 7. 近期实施计划

### Phase 2a：博客源 live 验证（当前优先）

1. 逐个 live 验证 3 个已有博客爬虫
2. 修复 HTML selector 漂移问题（如有）
3. 博客数据走完全流程：crawl → normalize → enrich → llm-relevance → score → report
4. 验证博客在报告中的排序和呈现是否合理

### Phase 2b：GitHub Advisory 爬虫

1. 实现 GitHub Advisory 爬虫（GraphQL API）
2. 接入 normalize pipeline
3. authority 打分暂用 CVSS 映射

### Phase 2c：调度器

在 Phase 2a/2b 完成、日更数据源就绪后，实现调度器：
- 基于 Python 标准库 while-loop + sleep
- 博客/漏洞公告每天爬取
- 论文状态检测每天轻量 check
- graceful shutdown（SIGINT/SIGTERM）
- 运行日志 RotatingFileHandler
