# Report Specification

## 1. Overview

报告是用户与系统的主要交互界面。设计原则：

- **用户时间有限**：每天 5-10 分钟，每周 1-2 小时
- **内容量可消化**：推荐的量必须是用户能看完的
- **分类清晰**：不同类型内容（论文/博客/漏洞）分栏展示
- **已读过滤**：用户标记已读后，后续报告不再重复推荐
- 格式：Markdown，便于 git 版本控制和任何编辑器查看

---

## 2. 日报 vs 周报的定位

| 维度 | 日报 | 周报 |
|------|------|------|
| 时间投入 | 5-10 分钟 | 1-2 小时 |
| 内容类型 | 博客 + 漏洞公告（日更源） | 论文精选推荐 |
| 推荐数量 | 博客 3-5 篇 + 漏洞速报 3-5 条 | 论文 5-10 篇 |
| 论文是否出现 | **不出现**，除非当天有状态机更新 | 主要内容 |
| 反馈收集 | 无 | 用户主动反馈已读论文和评价 |

---

## 3. Daily Report (日报)

### 3.1 文件命名
`data/reports/daily/YYYY-MM-DD.md`

### 3.2 报告结构

```markdown
# Research Radar - 日报
**日期**: YYYY-MM-DD
**生成时间**: YYYY-MM-DD HH:MM

---

## 今日博客推荐（N 篇）

### 1. [博客标题]
- **来源**: PortSwigger Research
- **发布**: YYYY-MM-DD
- **相关度**: 0.85
- **URL**: [link]
- **摘要**: 一段话摘要...

### 2. [博客标题]
...

---

## 漏洞速报（N 条）
（Phase 2b 实现后启用）

### 1. [CVE-XXXX-XXXXX: 漏洞标题]
- **CVSS**: 9.8
- **影响**: 受影响产品/组件
- **URL**: [link]

---

## 论文动态
（仅在检测到顶会状态机更新时展示）

> CCS 2026 Cycle 1 通知已发布，新增 XX 篇论文。详见周报。

或：

> 今日无论文更新。

---

## 统计
- 今日新增博客: X 篇
- 今日新增漏洞: Y 条
- 数据库总量: Z 条
```

### 3.3 日报生成逻辑

1. **博客推荐**：从近 3 天内新增的 BLOGS 类型 artifact 中，按 final_score 降序取前 5 篇（排除已标记 `read` 的）
2. **漏洞速报**：从近 3 天内新增的 ADVISORIES 类型 artifact 中，按 CVSS/score 降序取前 5 条（Phase 2b 后启用）
3. **论文动态**：检查当天是否有新的 PAPERS 类型 artifact 入库（状态机更新），有则提示，无则显示"无更新"
4. 过滤逻辑：已标记 `read` 的 artifact 不再出现在推荐列表中

---

## 4. Weekly Report (周报)

### 4.1 文件命名
`data/reports/weekly/YYYY-WXX.md`

### 4.2 报告结构

```markdown
# Research Radar - 周报
**周**: YYYY-WXX
**周期**: YYYY-MM-DD 至 YYYY-MM-DD
**生成时间**: YYYY-MM-DD HH:MM

---

## 本周论文推荐阅读（N 篇）

从本周及历史高相关度论文中精选，优先推荐未读论文。

### 1. [论文标题]
- **来源**: USENIX Security 2025
- **评分**: 0.95 (recency: 1.00, authority: 1.00, relevance: 0.84)
- **URL**: [link]
- **摘要**: 论文摘要（200-300 字）...

### 2. [论文标题]
...

---

## 本周博客回顾

本周共收录 X 篇博客文章。

| # | 标题 | 来源 | 相关度 | 状态 |
|---|------|------|--------|------|
| 1 | [标题] | PortSwigger | 0.85 | 未读 |
| 2 | [标题] | Project Zero | 0.72 | 已读 |
| ... | | | | |

---

## Relevance 分档统计

- 高相关 (>= 0.6): N items
- 中等 (0.3 - 0.6): N items
- 低相关 (< 0.3): N items

---

## Score Distribution

- >= 0.9: N items
- 0.8-0.9: N items
- 0.7-0.8: N items
- 0.6-0.7: N items
- < 0.6: N items

---

## 统计
- 本周新增论文: X 篇
- 本周新增博客: Y 篇
- 数据库总量: Z 条
```

### 4.3 周报生成逻辑

1. **论文推荐**：从所有未读的 high-relevance PAPERS（relevance >= 0.6）中，按 final_score 降序取前 10 篇
2. **博客回顾**：本周新增的 BLOGS 类型 artifact，按 relevance 排序，表格形式展示，标注已读/未读
3. **统计**：score distribution + relevance distribution（保留现有逻辑）
4. 过滤逻辑：论文推荐优先未读内容；已读论文不出现在推荐区

---

## 5. 已读追踪机制

### 5.1 交互方式

通过 CLI 标记已读：

```bash
python -m src.cli feedback --artifact-id 123 --type read
python -m src.cli feedback --artifact-id 123 --type read --note "很有启发，和我的方向高度相关"
```

### 5.2 实现

- FeedbackType 枚举新增 `READ = "read"`
- feedback CLI 的 `--type` 选项增加 `read`
- 报告生成时查询 feedback_events 表，排除 target_type=artifact + feedback_type=read 的 artifact

### 5.3 反馈闭环

用户每周主动通过 CLI 反馈：
- `feedback --type read`：标记已读
- `feedback --type like`：标记喜欢（提升后续推荐权重）
- `feedback --type dislike`：标记不喜欢（降低后续推荐权重）
- `feedback --type note --note "..."`：附加评论

---

## 6. Report Storage

```
data/reports/
├── daily/
│   ├── 2026-03-13.md
│   └── ...
└── weekly/
    ├── 2026-W11.md
    └── ...
```

所有报告保留历史，便于回顾和对比。
