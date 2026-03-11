# Source Plan

## 1. Overview

数据源按重要性分为三个优先级：
- **P0 (核心)**: 四大顶会论文、高质量博客
- **P1 (重要)**: 软工顶会安全track、arXiv
- **P2 (次要)**: 漏洞数据库（简单统计）

---

## 2. Papers (P0/P1)

### 2.1 四大顶会 (P0) — 已实现

#### IEEE S&P (Oakland)
- **URL**: https://www.ieee-security.org/
- **频率**: 每年5月

#### ACM CCS
- **URL**: https://www.sigsac.org/ccs/
- **频率**: 每年10-11月
- **注意**: 官方页面依赖前端加载，已实现 DBLP fallback

#### USENIX Security
- **URL**: https://www.usenix.org/conference/usenixsecurity
- **频率**: 每年8月

#### NDSS
- **URL**: https://www.ndss-symposium.org/
- **频率**: 每年2-3月

### 2.2 软工顶会安全track (P1) — 未实现

- ICSE, FSE, ASE 的 Security track
- 评分已预留 source_tier 支持

### 2.3 arXiv (P1) — 未实现

- **API**: arXiv API
- **分类**: cs.CR (Cryptography and Security)
- 评分已预留衰减曲线

---

## 3. Blogs (P0) — 已实现

| 博客 | URL | 说明 |
|------|-----|------|
| PortSwigger Research | https://portswigger.net/research | Web安全研究 |
| Google Project Zero | https://googleprojectzero.blogspot.com/ | 漏洞研究 |
| Cloudflare Blog | https://blog.cloudflare.com/ | 安全+基础设施 |

---

## 4. Advisories (P2) — 未实现

根据用户反馈，漏洞数据库对科研价值有限（垃圾信息较多），可延后。

- NVD (National Vulnerability Database)
- GitHub Security Advisories

---

## 5. Future Sources

以下数据源可在 MVP 后考虑：
- Twitter/X: 安全研究者动态
- Reddit: r/netsec, r/websecurity
- Google Scholar / Semantic Scholar: 引用追踪
- GitHub Trending: 安全工具

---

## 6. Multi-Year Crawling Strategy

**建议范围**: 2022-2026（5年）

- 最新论文（2025-2026）：前沿方向和新兴趋势
- 近期论文（2023-2024）：已有讨论和验证
- 历史论文（2022）：趋势对比和演化视角
