# Scoring Strategy

## 1. Overview

评分系统的目标是在LLM上下文窗口限制下，优先保留和推荐最有价值的内容。

> **v2 重构 (2026-03-16)**：从单一评分公式改为分轨评分。学术轨和工业轨使用不同权重配置，不再混排。

### 1.1 分轨评分公式（v2）

**学术轨**（T1 顶会 + T2 arXiv）：
```
academic_score = domain_relevance × 0.5 + recency × 0.3 + authority × 0.2
```
用于决定哪些论文进入 L2 深度分析和聚类。

**工业轨**（T3 博客 + T4 未来快速源）：
```
industry_score = recency × 0.5 + domain_relevance × 0.4 + authority × 0.1
```
用于决定哪些博客进入需求信号提取。

### 1.2 历史公式（v1，deprecated）

```
final_score = recency × 0.4 + authority × 0.3 + relevance × 0.3
relevance = keyword_match × 0.4 + llm_relevance × 0.6
```

v1 公式保留在代码中作为 fallback，当 artifact 的 source_tier 无法识别轨道时使用。

然后根据历史反馈调整：
```
adjusted_score = final_score × feedback_multiplier
```

---

## 2. Recency Score (时效性评分)

### 2.1 设计原则
时效性衰减应该根据**内容类型和权威性**调整，而不是一刀切。

### 2.2 四大顶会论文
```
近1年:   1.0
1-2年:   0.95
2-3年:   0.90
3-5年:   0.80
5年以上: 0.60
```

**理由**：四大一年一次，近3年的论文都应保持高权重。

### 2.3 软工顶会安全track
```
近1年:   1.0
1-2年:   0.90
2-3年:   0.80
3年以上: 0.60
```

### 2.4 高质量博客
```
近1个月:  1.0
1-3个月:  0.95
3-6个月:  0.90
6-12个月: 0.80
1年以上:  0.60
```

**理由**：高质量博客更新周期约3-4个月，不应快速衰减。


### 2.5 arXiv预印本
```
近1个月:  1.0
1-3个月:  0.80
3-6个月:  0.60
6个月以上: 0.40
```

**理由**：arXiv更新快，且可能被正式发表版本替代，可以快速衰减。

### 2.6 高危漏洞
```
近1周:   1.0
1-4周:   0.95
1-3个月: 0.90
3-6个月: 0.80
6个月以上: 0.70
```

**理由**：漏洞有时效性，但高危漏洞的研究价值持续较长。

---

## 3. Authority Score (权威性评分)

### 3.1 Papers
- 四大顶会 (S&P, CCS, USENIX Security, NDSS): **1.0**
- 软工顶会安全track (ICSE, FSE, ASE): **0.8**
- arXiv预印本: **0.5**

### 3.2 Blogs
- 暂不区分权威性，统一为: **0.7**
- 后续可根据来源细分（如PortSwigger: 0.9）

### 3.3 Advisories
- 高危漏洞 (CVSS >= 7.0): **0.9**
- 中危漏洞 (CVSS 4.0-6.9): **0.7**
- 低危漏洞 (CVSS < 4.0): **0.5**


---

## 4. Relevance Score (研究相关度评分)

### 4.1 v4 宽泛领域过滤（当前）

> **v2 变更 (2026-03-16)**：Profile 放宽后 `preferred_topics` 为空，keyword match 组件停用。relevance 完全由 LLM domain filter 决定。

```
relevance_score = llm_domain_relevance_score (v4)
```

LLM prompt 从「这跟 web-security 相关吗？」变为「这是安全/软件工程领域的吗？」——宽泛领域过滤，目标是保留所有可能有价值的内容，让下游分析（聚类、空白检测）决定价值。

评分标准：
- 5 = 安全或软件工程核心问题
- 4 = 安全或软件工程的重要子领域
- 3 = 与安全/SE 有明确交叉
- 2 = 边缘相关
- 1 = 不相关或属于回避列表

### 4.2 v3 混合计算方式（deprecated，代码保留）
```
relevance_score = (keyword_match_score × 0.4) + (llm_relevance_score × 0.6)
```

v3 版本在 Profile 有具体 `preferred_topics` 时使用。当 `preferred_topics` 为空时自动降级为纯 LLM domain filter。


---

## 5. Feedback Multiplier (反馈调整系数)

### 5.1 初始值设定
基于用户的历史反馈调整评分：

**Artifact级别反馈**：
- 用户标记"感兴趣": **×1.2**
- 用户标记"不感兴趣": **×0.5**
- 无反馈: **×1.0**

**主题级别反馈**：
- 用户确认主题为核心关注: 该主题下所有artifacts **×1.15**
- 用户标记主题不感兴趣: 该主题下所有artifacts **×0.6**

**方向级别反馈**：
- 用户对某个candidate_direction评价很高: 相关artifacts **×1.3**
- 用户明确拒绝某个方向: 相关artifacts **×0.4**

### 5.2 反馈传播
当用户对某个artifact提供反馈后：
1. 直接影响该artifact的评分
2. 学习到user_profile中
3. 影响后续相似内容的relevance_score计算

---

## 6. Score Update Strategy

### 6.1 活跃窗口（最近30天）
- 用户反馈后，下次批处理时重新计算评分
- 重新计算包括：relevance_score和feedback_multiplier

### 6.2 历史内容（30天前）
- 标记为"待重评"，不立即处理
- 用户可手动触发"全量重评"
- 或当某个主题/方向变得重要时，重评相关内容

### 6.3 未来内容
- 自动应用最新的profile和反馈模式
- 初始评分即包含学习到的偏好


---

## 7. Context Window Management

### 7.1 基于评分的内容保留策略

**高权重内容（score >= 0.8）**：
- 保留完整摘要（500-1000 tokens）
- 保留关键引用和上下文

**中权重内容（0.5 <= score < 0.8）**：
- 保留压缩摘要（200-300 tokens）
- 保留核心观点

**低权重内容（score < 0.5）**：
- 仅保留元数据（标题、来源、评分）
- 或直接淘汰

### 7.2 动态阈值调整
当上下文接近限制时：
1. 提高保留阈值（如从0.5提升到0.6）
2. 压缩更多中权重内容
3. 淘汰更多低权重内容

---

## 8. Example Calculation

### 示例：一篇四大论文
- **来源**: USENIX Security 2025
- **发布时间**: 6个月前
- **标题**: "A New Approach to Detecting XSS in Modern Web Applications"

**计算过程**：
1. Recency Score: 0.95 (近1年的四大论文)
2. Authority Score: 1.0 (四大顶会)
3. Relevance Score:
   - Keyword Match: 1.0 (包含"XSS"和"Web Applications")
   - LLM Score: 0.8 (评分4/5)
   - Combined: 0.4×1.0 + 0.6×0.8 = 0.88
4. Final Score: 0.4×0.95 + 0.3×1.0 + 0.3×0.88 = 0.944

如果用户之前对XSS相关内容表示感兴趣：
- Adjusted Score: 0.944 × 1.2 = **1.13** (cap at 1.0 = **1.0**)

**结论**：这是一篇高优先级内容，应保留完整信息。
