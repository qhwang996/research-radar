# Report Specification

## 1. Overview

报告是用户与系统的主要交互界面。设计原则：

- **用户时间有限**：每天 5-10 分钟，每周 1-2 小时
- **内容量可消化**：推荐的量必须是用户能看完的
- **分类清晰**：不同类型内容（论文/博客/漏洞）分栏展示
- **已读过滤**：用户标记已读后，后续报告不再重复推荐
- 格式：Markdown，便于 git 版本控制和任何编辑器查看

---

## 2. 日报 vs Landscape 全景报告的定位

| 维度 | 日报 | Landscape 全景报告 |
|------|------|-------------------|
| 时间投入 | 5-10 分钟 | 1-2 小时 |
| 内容类型 | 博客 + 漏洞公告（日更源） | 研究前沿地图 + 趋势洞察 + 候选方向 + 推荐阅读 |
| 核心价值 | 快速感知业界动态 | 理解领域全貌、发现研究空白、收敛研究方向 |
| 论文是否出现 | **不出现**，除非当天有状态机更新 | 主要内容（按主题聚类组织，非平坦列表） |
| 反馈收集 | 无 | 用户对方向和主题反馈 |

> **注意**：Landscape 报告替换了原周报（Section 4）。原周报代码保留但标记 deprecated。

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

## 4. Landscape Report (研究前沿全景报告) — 替换原周报

### 4.1 文件命名
`data/reports/weekly/YYYY-WXX.md`（复用周报目录）

### 4.2 依赖
需要智能分析层（Phase 3 v2）就绪：Theme 聚类 + 趋势分析 + 空白检测 + 候选方向。详见 `09_intelligence_layer.md`。

> **实现状态 (2026-03-16)**：`src/reporting/landscape.py` 已实现，包含空白分析 section。通过 `report --type landscape` 或 `run --full` 生成。

### 4.3 报告结构

```markdown
# Research Radar - 研究前沿全景报告
**周**: YYYY-WXX
**周期**: YYYY-MM-DD 至 YYYY-MM-DD
**生成时间**: YYYY-MM-DD HH:MM

---

## 研究前沿地图

当前追踪 N 个研究子领域，涵盖 M 篇高相关论文。

### 1. [Theme Name] ▲ 上升趋势
- **论文数**: 2022: X | 2023: Y | 2024: Z | 2025: W
- **代表方法**: method1, method2, method3
- **关键开放问题**:
  - 问题1...
  - 问题2...
- **代表论文**: [Paper A] (USENIX 2025), [Paper B] (CCS 2024)

### 2. [Theme Name] — 稳定
...

---

## 趋势洞察

### 上升领域
- [Theme]: 近两年论文数增长 X%，关键驱动...

### 方法论演进
- 从 X 方法向 Y 方法转变...

### 研究空白
- **空白 1**: 多篇论文提到但未解决...
- **空白 2**: ...

---

## 学术-工业空白分析

以下是工业界已在关注但学术界尚未充分解决的领域：

### 空白 1: [Topic]  (gap_score: X.XX)
- **工业需求**: N 个独立来源提到
  - [Blog A] (PortSwigger) — 描述...
- **学术覆盖**: 当前覆盖度 XX%
- **空白性质**: 为什么这是一个研究机会

---

## 候选研究方向

### 方向 1: [Direction Title]
- **概述**: ...
- **为什么现在**: ...
- **新颖性**: ★★★★☆  |  **影响力**: ★★★★★  |  **可行性**: ★★★☆☆
- **支撑论文**:
  - [Paper A] (USENIX 2025) — 贡献...
  - [Paper B] (CCS 2024) — 贡献...
- **待解决问题**:
  - 问题1...
- **建议下一步**: ...

### 方向 2: [Direction Title]
...

---

## 推荐阅读

支撑以上方向的论文，按优先级排序（排除已读）。

| # | 标题 | 来源 | 关联方向 | 相关度 | 状态 |
|---|------|------|----------|--------|------|
| 1 | ... | USENIX 2025 | 方向1 | 0.95 | 未读 |

---

## 本周博客回顾

| # | 标题 | 来源 | 相关度 | 状态 |
|---|------|------|--------|------|
| 1 | ... | PortSwigger | 0.85 | 未读 |

---

## 统计
- 高相关论文总数: X（已深度分析: Y）
- 研究子领域数: Z
- 累计候选方向数: W
- 数据库总量: T
```

### 4.4 Landscape 报告生成逻辑

1. **研究前沿地图**：从 `themes` 表加载所有 `status IN (candidate, core)` 的 Theme，按 `artifact_count` 降序排列
2. **趋势洞察**：从 Theme 的 `trend_direction`、`methodology_tags`、`open_questions` 提取
3. **学术-工业空白分析**：从 `research_gaps` 表加载 `status == active` 的空白，按 `gap_score` 降序
4. **候选方向**：从 `candidate_directions` 表加载 `status == active` 方向
5. **推荐阅读**：全库未读高分论文，按 `final_score` 降序排列
6. **博客回顾**：近期 BLOGS 类型 artifact，表格形式展示
7. 已读过滤：所有推荐列表排除 `FeedbackType.READ` 标记的 artifact

### 4.5 原周报（Deprecated）

原 `WeeklyReportGenerator` 代码保留但不再作为默认周报生成器。如需回退，可通过 `report --type weekly-legacy` 调用。

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

**Artifact 级反馈**：
- `feedback --artifact-id 123 --type read`：标记已读
- `feedback --artifact-id 123 --type like`：标记喜欢
- `feedback --artifact-id 123 --type dislike`：标记不喜欢
- `feedback --artifact-id 123 --type note --note "..."`：附加评论

**Theme 级反馈**（Phase 3）：
- `feedback --theme-id UUID --type like`：确认主题有价值（提升为 CORE）
- `feedback --theme-id UUID --type dislike`：标记不感兴趣

**Direction 级反馈**（Phase 3）：
- `feedback --direction-id UUID --type like`：标记方向有前景
- `feedback --direction-id UUID --type note --note "..."`：对方向附加评论

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
