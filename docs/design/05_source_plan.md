# Source Plan

## 1. 数据源分层

数据源按权威性和更新频率分为两个维度：

### 1.1 权威性分层（Source Tier）

> **v2 重构 (2026-03-16)**：Tier 体系调整为与双轨架构对齐。原 T2（博客）→ T3，新增 T2（arXiv）。
> 详见 `09_intelligence_layer.md` 的 SourceTier 枚举。

| Tier | 枚举值 | 信息轨道 | 类型 | 示例 | authority | 说明 |
|------|--------|---------|------|------|-----------|------|
| T1 | `t1-conference` | 学术轨 | 顶会论文 | NDSS, S&P, CCS, USENIX Security | 1.0 | 经过同行评审，最高权威性 |
| T2 | `t2-arxiv` | 学术轨 | arXiv 预印本 | cs.CR, cs.SE, cs.PL | 0.5 | 最新研究，未经评审，能看到趋势萌芽 |
| T3 | `t3-research-blog` | 工业轨 | 知名安全研究博客 | Project Zero, PortSwigger, Cloudflare | 0.7 | 机构背书，代表工业需求信号 |
| T4 | `t4-personal` | 工业轨 | 个人/公司博客 | 用户指定 | 待设计 | 快速热点，质量参差不齐 |

**当前实现**：T1（已有爬虫）+ T3 博客（已有爬虫，已 live 验证，55 条入库）
**Phase A 新增**：T2 arXiv 爬虫
**未来**：T4 个人博客/公众号（用户后续提供具体源）

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

### 2.6 arXiv (T2) — Phase A 新增

**API**：arXiv Atom API (`https://export.arxiv.org/api/query`)
**分类**：cs.CR (Cryptography and Security) + cs.SE (Software Engineering) + cs.PL (Programming Languages)
**时间范围**：最近 12 个月（趋势检测需要足够的时间跨度）
**预计数据量**：~5000-8000 篇/年（经域过滤后进入分析的约 1000-2000 篇）
**Rate limit**：每请求间隔 3 秒（arXiv 政策要求）
**增量爬取**：追踪上次爬取时间，每日增量获取
**Tier 值**：`t2-arxiv`（学术轨，authority=0.5）
**衰减曲线**：见 Section 2.5（近1月 1.0，6月+ 0.40）

ArxivCrawler 设计要点：
- 扩展 `PaperCrawler` 基类
- 解析 Atom XML 响应
- 提取：title, authors, abstract, published_date, arxiv_id, categories, pdf_url
- arxiv_id 作为 external_id 用于去重
- 分页处理（每页 100 条）
- 注册到 `src/crawlers/registry.py`

---

## 3. Blogs (T3)

### 3.1 已实现爬虫（已 live 验证，55 条入库）

| 博客 | URL | 说明 | source_tier |
|------|-----|------|-------------|
| PortSwigger Research | https://portswigger.net/research | Web 安全研究 | t3-research-blog |
| Google Project Zero | https://googleprojectzero.blogspot.com/ | 漏洞研究 | t3-research-blog |
| Cloudflare Security Blog | https://blog.cloudflare.com/tag/security/ | 安全+基础设施 | t3-research-blog |

**v2 定位变更**：博客不再与论文混排。博客属于工业轨，其核心价值是**需求信号**（工业界遇到了什么问题），通过 `SignalExtractionPipeline` 提取结构化需求信号，用于与学术覆盖交叉比对（空白检测）。

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

## 5. 个人/公司博客 (T4) — 待用户提供

用户确认有具体想追踪的个人博客/公众号，将在后续提供 URL。

T4 源属于工业轨，接入后同样通过 `SignalExtractionPipeline` 提取需求信号。

设计架构已预留 T4 支持（`SourceTier.T4_PERSONAL` 枚举），新增源只需：
1. 实现爬虫（扩展 `BaseCrawler`）
2. 注册到 `registry.py`
3. normalization tier 映射中加入 `t4-personal`

暂不纳入当前实施计划，等用户提供具体源。

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

## 7. 近期实施计划（v2 更新）

### Phase A：基础改造（当前优先）

1. **A1**: SourceTier 枚举正式化 + 已有数据 tier 值迁移
2. **A2**: Profile V2（放宽关键词）+ 宽泛相关度评分 v4
3. **A3**: arXiv 爬虫（cs.CR + cs.SE + cs.PL）

### Phase B：工业信号轨道

4. **B1**: 需求信号提取 pipeline（博客 → 结构化需求信号）
5. **B2**: 分轨评分（学术轨 / 工业轨 不同权重）

### Phase C-D：空白检测 + 方向综合

见 `09_intelligence_layer.md` Phase C-D。

### 降低优先级

- Phase 2b（GitHub Advisory 爬虫）— 降优，空白检测不依赖 advisory
- Phase 2c（调度器）— 降优，先手动运行验证全流程
