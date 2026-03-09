# Source Plan

## 1. Overview

数据源按重要性分为三个优先级：
- **P0 (核心)**: 四大顶会论文、高质量博客
- **P1 (重要)**: 软工顶会安全track、arXiv
- **P2 (次要)**: 漏洞数据库（简单统计）

---

## 2. Papers (P0/P1)

### 2.1 四大顶会 (P0)

#### IEEE S&P (Oakland)
- **URL**: https://www.ieee-security.org/
- **频率**: 每年5月
- **抓取方式**: 爬取会议官网论文列表
- **过滤策略**: LLM层次过滤（标题 → 摘要）

#### ACM CCS
- **URL**: https://www.sigsac.org/ccs/
- **频率**: 每年10-11月
- **抓取方式**: 爬取会议官网
- **过滤策略**: 同上

#### USENIX Security
- **URL**: https://www.usenix.org/conference/usenixsecurity
- **频率**: 每年8月
- **抓取方式**: 爬取会议官网
- **过滤策略**: 同上

#### NDSS
- **URL**: https://www.ndss-symposium.org/
- **频率**: 每年2-3月
- **抓取方式**: 爬取会议官网
- **过滤策略**: 同上


### 2.2 软工顶会安全track (P1)

#### ICSE (International Conference on Software Engineering)
- **URL**: https://conf.researchr.org/series/icse
- **频率**: 每年4-5月
- **关注**: Security track论文

#### FSE/ESEC (Foundations of Software Engineering)
- **URL**: https://conf.researchr.org/series/fse
- **频率**: 每年11-12月
- **关注**: Security相关论文

#### ASE (Automated Software Engineering)
- **URL**: https://conf.researchr.org/series/ase
- **频率**: 每年9-11月
- **关注**: Security相关论文

### 2.3 arXiv (P1)

- **URL**: https://arxiv.org/
- **API**: arXiv API (https://arxiv.org/help/api)
- **分类**: cs.CR (Cryptography and Security)
- **抓取频率**: 每天
- **过滤**: 关键词 + LLM相关性判断

---

## 3. Blogs (P0)

### 3.1 高质量博客列表

**注**: 具体博客列表待用户提供，以下为示例框架。


#### 安全公司博客
- **PortSwigger Research**: https://portswigger.net/research
  - RSS: 待确认
  - 抓取频率: 每天
  
- **Google Project Zero**: https://googleprojectzero.blogspot.com/
  - RSS: 待确认
  - 抓取频率: 每天

#### 其他博客
- 待用户补充...

### 3.2 博客抓取策略
- 优先使用RSS feed
- 无RSS则爬取HTML
- 保存完整文章内容
- LLM生成摘要

---

## 4. Advisories (P2)

### 4.1 重要性说明
根据用户反馈，漏洞数据库对科研价值有限：
- 含金量一般
- 垃圾信息较多
- 主要用于感受趋势，简单统计

**MVP策略**: 
- 简化处理，只做基础统计
- 不做深度分析
- 可延后实现


### 4.2 NVD (National Vulnerability Database)
- **URL**: https://nvd.nist.gov/
- **API**: NVD API 2.0
- **抓取内容**: 基础统计数据
- **处理方式**: 
  - 按月统计漏洞数量
  - 按类型分类（Web、系统、网络等）
  - 不做深度内容分析

### 4.3 GitHub Security Advisories
- **URL**: https://github.com/advisories
- **API**: GitHub GraphQL API
- **抓取内容**: 高影响力漏洞
- **处理方式**: 同NVD

---

## 5. Future Sources (可选)

以下数据源可在MVP后考虑：

### 5.1 社交媒体
- Twitter/X: 安全研究者动态
- Reddit: r/netsec, r/websecurity
- HackerNews: 安全相关讨论

### 5.2 其他学术资源
- Google Scholar: 引用追踪
- Semantic Scholar: 论文推荐
- DBLP: 作者追踪

### 5.3 开源项目
- GitHub Trending: 安全工具
- Security-focused repositories

**注**: MVP阶段不实现，待系统稳定后评估。


---

## 6. Implementation Priority

### Phase 1 (MVP核心)
1. **arXiv** - 有API，易实现，更新频繁
2. **2-3个高质量博客** - 用户提供列表后实现

### Phase 2 (扩展)
3. **四大顶会** - 爬取会议官网
4. **软工顶会安全track** - 同上

### Phase 3 (可选)
5. **漏洞数据库** - 简单统计
6. **其他数据源** - 按需添加

---

## 7. Crawler Configuration

### 7.1 配置文件结构
```json
{
  "sources": {
    "arxiv": {
      "enabled": true,
      "api_url": "https://export.arxiv.org/api/query",
      "category": "cs.CR",
      "fetch_frequency": "daily"
    },
    "blogs": [
      {
        "name": "PortSwigger Research",
        "url": "https://portswigger.net/research",
        "rss": "待确认",
        "enabled": true
      }
    ]
  }
}
```

### 7.2 用户待提供信息
- [ ] 博客完整列表（名称、URL、RSS）
- [ ] 是否需要特定关键词过滤
- [ ] 其他想要添加的数据源


---

## 8. Multi-Year Crawling Strategy

### 8.1 年份范围
**建议范围**: 2022-2026（5年）

**理由**：
- 最新论文（2025-2026）：代表最前沿方向和新兴趋势
- 近期论文（2023-2024）：已有一定讨论和验证
- 历史论文（2022）：提供趋势对比和演化视角
- 5年窗口：平衡前沿性和趋势分析

### 8.2 实现状态
- ✅ NDSS 2022-2026: 795篇
- ✅ S&P 2024-2026: 374篇
- ⏳ USENIX Security: 待实现
- ⏳ CCS: 待实现

### 8.3 总计
**1,169篇论文**（截至2026-03-09）

