# Report Specification

## 1. Overview

所有报告使用Markdown格式，便于：
- 版本控制（git）
- 任何编辑器查看
- 脚本处理和复用
- 长期保存

---

## 2. Daily Report (日报)

### 2.1 文件命名
`data/reports/daily/YYYY-MM-DD.md`

### 2.2 报告结构

```markdown
# Research Radar - Daily Report
**Date**: YYYY-MM-DD  
**Generated**: YYYY-MM-DD HH:MM

---

## Summary
- Total new artifacts: X
- High-value items (score >= 0.8): Y
- New themes discovered: Z

---

## By Theme

### [Theme Name 1]
**Artifacts**: N items

#### [Artifact Title 1]
- **Source**: Papers / Blogs / Advisories
- **Published**: YYYY-MM-DD
- **Score**: 0.95
- **URL**: [link]
- **Summary**: 
  LLM生成的摘要内容，200-300字...

#### [Artifact Title 2]
...

### [Theme Name 2]
...

---

## Uncategorized
未归类的高分内容...

---

## Action Items
- [ ] Review candidate theme: "XXX"
- [ ] Provide feedback on direction: "YYY"
```


### 2.3 日报生成逻辑
- 包含昨日新增的所有artifacts
- 按主题分组，主题内按评分排序
- 只显示score >= 0.6的内容
- 高分内容（>= 0.8）显示完整摘要
- 中分内容（0.6-0.8）显示简短摘要

---

## 3. Weekly Report (周报)

### 3.1 文件命名
`data/reports/weekly/YYYY-WXX.md`  
例如：`2026-W10.md`

### 3.2 报告结构

```markdown
# Research Radar - Weekly Report
**Week**: YYYY-WXX  
**Period**: YYYY-MM-DD to YYYY-MM-DD  
**Generated**: YYYY-MM-DD HH:MM

---

## Executive Summary
本周共处理X篇内容，发现Y个新主题，生成Z个候选研究方向。

---

## Statistics

### Content Breakdown
- Papers: X篇 (四大: A, 软工: B, arXiv: C)
- Blogs: Y篇
- Advisories: Z个 (高危: M, 中危: N)

### Score Distribution
- High (>= 0.8): X篇
- Medium (0.6-0.8): Y篇
- Low (< 0.6): Z篇

### Theme Activity
- Active themes: X
- New candidate themes: Y
- Archived themes: Z


---

## Top 10 High-Value Content

### 1. [Artifact Title]
- **Type**: Paper / Blog / Advisory
- **Score**: 0.98
- **Published**: YYYY-MM-DD
- **Theme**: [Theme Name]
- **URL**: [link]
- **Summary**: 
  详细摘要...
- **Why Important**: 
  LLM生成的重要性说明...

### 2. [Artifact Title]
...

---

## Candidate Research Directions

本周生成3个候选研究方向，请审核并提供反馈。

### Direction 1: [Direction Name]

#### Overview
**Thesis**: 核心论点...  
**Why Now**: 为什么现在是好时机...  
**Why Promising**: 为什么有前景（3-5年视角）...

#### Multi-dimensional Scoring
- **Novelty**: 4/5 - 新颖性评估
- **Impact**: 5/5 - 能支撑2-3篇四大论文
- **Feasibility**: 4/5 - 技术和时间可行性
- **Industrial Value**: 5/5 - 解决业界实际痛点
- **Technical Contribution**: 4/5 - 需要新工具/新方法


#### Supporting Evidence
**Key Papers** (3-5篇):
- [Paper Title 1] - USENIX Security 2025
- [Paper Title 2] - CCS 2024
- ...

**Industry Signals** (2-3个):
- [Blog/Advisory Title] - PortSwigger, 2026-02
- ...

**Related Themes**:
- Theme A (15 artifacts)
- Theme B (8 artifacts)

#### Feedback Section
**Pros** (待填写):
- 

**Cons** (待填写):
- 

**Unknowns** (待填写):
- 

**Personal Notes** (待填写):
- 

---

### Direction 2: [Direction Name]
(同样结构)

### Direction 3: [Direction Name]
(同样结构)

---

## Theme Evolution

### New Themes This Week
- **[Theme Name]**: X artifacts, 待确认
- ...

### Growing Themes
- **[Theme Name]**: 从X增长到Y artifacts
- ...

### Declining Themes
- **[Theme Name]**: 从X降至Y artifacts
- ...

```


### 3.3 周报生成逻辑
- 汇总本周所有artifacts
- 统计各维度数据
- 选出Top10高分内容
- LLM生成3个候选方向
- 分析主题演化

---

## 4. Monthly Report (月报，可选)

### 4.1 文件命名
`data/reports/monthly/YYYY-MM.md`

### 4.2 报告内容
- 月度统计和对比
- 趋势分析（主题热度变化）
- 方向收敛情况
- 反馈总结
- 下月计划

**注**：月报为可选功能，MVP阶段可不实现。

---

## 5. Report Generation Timing

- **Daily Report**: 每天早上6:00生成（前一天的内容）
- **Weekly Report**: 每周一早上6:00生成（上周内容）
- **Monthly Report**: 每月1号生成（上月内容）

---

## 6. Report Storage

```
data/reports/
├── daily/
│   ├── 2026-03-08.md
│   ├── 2026-03-09.md
│   └── ...
├── weekly/
│   ├── 2026-W10.md
│   ├── 2026-W11.md
│   └── ...
└── monthly/
    ├── 2026-03.md
    └── ...
```

所有报告保留历史，便于回顾和对比。

