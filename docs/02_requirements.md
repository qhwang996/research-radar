# Requirements

## 1. Core Constraints

### 1.1 LLM Context Window Management
**这是系统的核心约束和设计挑战。**

- 系统必须在LLM上下文窗口限制内运行
- Token消耗需要可控和可预测
- 需要设计权重机制和淘汰机制来管理上下文

#### 权重机制
不同权重的内容占用不同的上下文空间：
- 高权重内容：保留完整信息（全文/详细摘要）
- 中权重内容：保留压缩信息（简短摘要）
- 低权重内容：仅保留元数据或淘汰

#### 淘汰机制
三种机制协同工作：
1. **时间衰减**：超过阈值的内容自动降权或移除
2. **基于反馈**：用户标记为"不感兴趣"的内容直接淘汰
3. **基于收敛**：已归入candidate_direction的内容可压缩为引用

---

## 2. Data Volume and Frequency

### 2.1 Input Volume
- 数据量取决于LLM额度和上下文长度
- 优先保证质量而非数量
- 系统需要支持动态调整处理量

### 2.2 Report Frequency
- **Daily Report**: 每天查看
- **Weekly Report**: 每周查看深度分析

---

## 3. Research Focus

### 3.1 Current Domain
- 主要领域：Web应用安全
- 但系统设计应支持方向探索和转换

### 3.2 Selection Criteria
研究方向的选择标准（按优先级）：
1. **前景性**：能支撑2-3篇四大顶会论文的方向
2. **Taste**：个人品味和判断（在LLM时代比技能更重要）
3. **个人能力**：与现有技能栈的匹配度

### 3.3 User Profile
用户的个人信息和偏好应该：
- 作为可配置的文件或数据存储
- 支持灵活修改和扩充
- 包含以下维度：
  - 研究背景（当前方向、已发表论文）
  - 技能栈（擅长的技术、工具）
  - 兴趣关键词
  - 价值观（理论创新 vs 实用价值）

**更新方式**：手动编辑配置文件

---

## 4. Content Scoring

### 4.1 Scoring Factors (按重要性排序)
1. **时效性**：最近的内容权重更高
2. **研究相关度**：与用户profile的匹配程度
3. **历史反馈**：基于用户过往反馈的学习

### 4.2 Source Authority Weights

#### Papers
- **四大顶会** (S&P, CCS, USENIX Security, NDSS): 最高权重，彼此相当
- **软工顶会安全track** (ICSE, FSE, ASE等): 次高权重
- **arXiv预印本**: 较低权重

#### Blogs
- 暂不区分权威性
- 包括：
  - 安全公司博客（如PortSwigger）
  - 顶级黑客个人博客
  - 顶级安全团队博客

#### Advisories
- 高危漏洞：高权重
- 普通漏洞：中等权重

---

## 5. Data Sources

### 5.1 Papers
- **四大顶会**: S&P, CCS, USENIX Security, NDSS
- **软工顶会安全track**: ICSE, FSE, ASE等
- **arXiv**: 安全相关预印本

### 5.2 Blogs
用户提供博客列表，包括：
- 安全公司官方博客
- 个人安全研究者博客

### 5.3 Advisories
- NVD (National Vulnerability Database)
- GitHub Security Advisories

### 5.4 Bookmarks
- MVP阶段暂不实现

---

## 6. Data Ingestion

### 6.1 Automation Level
**半自动模式**：
- 用户提供base网站/RSS源
- 系统设计针对不同类型的爬虫器
- 系统定期自动抓取更新

### 6.2 Crawler Requirements
- 支持多种数据源格式（RSS, HTML, API）
- 保存原始数据以支持重新解析
- 记录抓取时间和元数据

---

## 7. Feedback Mechanism

### 7.1 Feedback Frequency
- 每天：快速反馈
- 每周：深度反馈

### 7.2 Feedback Format
对于每个artifact或candidate_direction，用户可以提供：
- **Pros**: 优点、吸引人的地方
- **Cons**: 缺点、不足之处
- **Personal Notes**: 个人看法和思考

### 7.3 Feedback Usage
- 调整后续内容的权重
- 学习用户偏好
- 影响candidate_direction的收敛

---

## 8. High-Value Content Criteria

系统应优先推荐以下类型的内容：
1. 顶会论文（四大 + 软工顶会安全track）
2. 高危漏洞报告
3. 顶级黑客的博客文章
4. 顶级安全团队的技术博客

---

## 9. MVP Scope

### 9.1 Must Have
- 支持Papers, Blogs, Advisories三类数据源
- 基本的权重和淘汰机制
- Daily和Weekly报告生成
- Pros/Cons反馈收集

### 9.2 Nice to Have
- Bookmarks支持
- 自动学习用户偏好
- 更复杂的主题聚类

### 9.3 Out of Scope
- 多用户支持
- 实时通知
- 移动端应用

---

## 10. LLM Budget and Model Selection

### 10.1 Budget
- **月度预算上限**: $100
- **目标成本**: $20-50/月
- **最小可接受**: $10/月（降低处理量）

### 10.2 Model Selection Strategy

#### 主力模型（日常处理）
- **GPT-4o** 或 **Claude 3.5 Sonnet**
- 用于：摘要生成、相关性判断、主题提取
- 成本效益比最优

#### 高质量模型（关键任务）
- **GPT-4 Turbo** 或 **Claude Opus**
- 用于：候选方向生成、深度分析
- 每周使用，成本可控

#### 快速筛选模型（可选）
- **GPT-4o-mini** ($0.15/1M输入)
- 用于：初步过滤、关键词扩展
- 大幅降低成本

### 10.3 Token Usage Estimation

#### 日常处理（每天20-30篇内容）
- 摘要生成: ~40k tokens/天
- 相关性判断: ~15k tokens/天
- 主题提取: ~10k tokens/天
- **日均成本**: $0.5-1.5

#### 周度任务
- 候选方向生成: ~50k tokens/周
- 周报生成: ~20k tokens/周
- **周均成本**: $2-5

#### 月度总计
- **预估**: $20-50/月
- **峰值**: 不超过$100/月

