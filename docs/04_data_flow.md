# Data Flow

## 1. Overview

系统采用**批处理模式**，以优化LLM token使用和成本控制。

核心数据流：
```
Source → Raw Data → Artifact → Theme → Candidate Direction → Report → Feedback → Profile Update
```

---

## 2. Data Ingestion (数据摄入)

### 2.1 Crawling Schedule
- **定时批处理**：每天23:00自动运行
- **手动触发**：紧急情况可手动执行

### 2.2 Crawling Process
```
1. 爬虫从配置的源抓取新内容
   ├─ Papers: 四大顶会 + 软工顶会 + arXiv
   ├─ Blogs: 用户配置的博客列表
   └─ Advisories: NVD + GitHub Security

2. 保存原始数据到 data/raw/
   ├─ 保留完整HTML/JSON
   ├─ 记录抓取时间戳
   └─ 记录source元数据

3. 去重检查
   └─ 基于URL/DOI避免重复处理
```

---

## 3. Artifact Generation (结构化处理)

### 3.1 Batch Processing
每次批处理时：
```
1. 读取所有新的raw data
2. 批量调用LLM生成摘要
   └─ 优化：一次prompt处理多篇相关内容
3. 提取元数据（作者、时间、来源等）
4. 保存为结构化artifact
```

### 3.2 Artifact Schema
每个artifact包含：
- `id`: 唯一标识
- `source_type`: papers/blogs/advisories
- `url`: 原始链接
- `title`: 标题
- `authors`: 作者（如适用）
- `published_date`: 发布时间
- `fetched_date`: 抓取时间
- `raw_content_path`: 原始数据路径
- `summary`: LLM生成的摘要
- `initial_score`: 初始评分
- `current_score`: 当前评分（会随反馈更新）
- `tags`: 标签列表
- `status`: active/archived/rejected

---

## 4. Scoring (评分)

### 4.1 Initial Scoring
新artifact的初始评分基于：

1. **时效性权重** (40%)
   - 最近1周: 1.0
   - 1-4周: 0.8
   - 1-3个月: 0.6
   - 3个月以上: 0.4

2. **来源权威性** (30%)
   - 四大顶会: 1.0
   - 软工顶会安全track: 0.8
   - 高危漏洞: 0.9
   - 知名博客: 0.7
   - arXiv: 0.5

3. **研究相关度** (30%)
   - 基于用户profile匹配
   - 关键词重叠度
   - 领域匹配度

### 4.2 Score Update Triggers
评分会在以下情况更新：
- 用户反馈后（活跃窗口内容）
- 手动触发全量重评
- 主题归类后（相关性调整）

---

## 5. Theme Extraction (主题提取)

### 5.1 混合模式
```
核心主题库（手动维护）
    ↓
匹配已知主题 → 归类到existing theme
    ↓
未匹配内容 → LLM提取新主题候选
    ↓
待确认主题列表 → 用户每周审核
    ↓
确认后加入核心主题库
```

### 5.2 Theme Schema
- `theme_id`: 主题ID
- `name`: 主题名称
- `keywords`: 关键词列表
- `status`: core/candidate/archived
- `artifact_count`: 关联的artifact数量
- `created_date`: 创建时间
- `last_updated`: 最后更新时间


### 5.3 Theme Snapshot
定期生成theme_snapshot记录：
- 某个时间点的主题状态
- 关联的artifacts
- 主题的演化趋势

---

## 6. Candidate Direction Generation (候选方向生成)

### 6.1 Generation Process
```
每周批处理：
1. 分析活跃themes的关联性
2. LLM识别可能的研究方向
3. 生成candidate_direction列表
4. 用户审核和调整
```

### 6.2 Candidate Direction Schema
- `direction_id`: 方向ID
- `name`: 方向名称
- `description`: 详细描述
- `related_themes`: 关联的主题列表
- `supporting_artifacts`: 支撑材料
- `potential_score`: 潜力评分（能支撑几篇论文）
- `feasibility_score`: 可行性评分
- `status`: active/under_review/archived
- `user_feedback`: 用户的pros/cons/notes

---

## 7. Report Generation (报告生成)

### 7.1 Daily Report
每天早上生成，包含：
- 昨日新增的高分artifacts
- 需要关注的新主题
- 快速浏览列表

### 7.2 Weekly Report
每周生成，包含：
- 本周artifact统计和趋势
- 主题演化分析
- 新的candidate_direction建议
- 需要用户反馈的内容


---

## 8. Feedback Loop (反馈循环)

### 8.1 Feedback Collection
用户可以对以下内容提供反馈：
- **Artifact级别**: 标记为感兴趣/不感兴趣
- **Theme级别**: 调整主题重要性
- **Direction级别**: 提供pros/cons/notes

### 8.2 Feedback Processing Strategy

#### 活跃窗口（最近30天）
- 用户反馈立即生效
- 下次批处理时重新评分
- 影响相关内容的权重

#### 历史内容（30天前）
- 标记为"待重评"
- 不立即处理（节省token）
- 用户可手动触发"全量重评"

#### 未来内容
- 自动应用最新偏好模型
- 基于历史反馈调整评分

### 8.3 Feedback Event Schema
- `feedback_id`: 反馈ID
- `target_type`: artifact/theme/direction
- `target_id`: 目标对象ID
- `feedback_type`: like/dislike/pros/cons/note
- `content`: 反馈内容
- `timestamp`: 反馈时间

---

## 9. Profile Update (用户画像更新)

### 9.1 Profile Snapshot
定期生成profile_snapshot：
- 用户当前的研究兴趣
- 偏好的主题和方向
- 反馈历史统计
- 用于后续内容推荐

### 9.2 Update Frequency
- 每次用户提供反馈后更新
- 每周生成完整快照
- 支持手动编辑配置文件


---

## 10. Data Retention and Archival (数据保留和归档)

### 10.1 Retention Policy
- **Raw data**: 永久保留（支持重新解析）
- **Active artifacts**: 保留在活跃窗口（30天）
- **Archived artifacts**: 移至归档，保留元数据
- **Rejected artifacts**: 保留ID和拒绝原因

### 10.2 Archival Triggers
- 时间衰减：超过阈值自动归档
- 用户反馈：标记为不感兴趣
- 已收敛：归入direction后压缩

---

## 11. Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Daily Batch Process                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────┐         ┌──────────┐         ┌──────────────┐
│   Crawlers  │────────→│ Raw Data │────────→│  Artifacts   │
│ (Papers/    │         │ Storage  │         │ (Structured) │
│  Blogs/     │         └──────────┘         └──────────────┘
│  Advisories)│                                      ↓
└─────────────┘                              ┌──────────────┐
                                             │   Scoring    │
                                             │  (Initial)   │
                                             └──────────────┘
                                                     ↓
                                             ┌──────────────┐
                                             │    Theme     │
                                             │  Extraction  │
                                             └──────────────┘
                                                     ↓
┌─────────────────────────────────────────────────────────────┐
│                   Weekly Batch Process                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
                      ┌──────────────┐
                      │  Candidate   │
                      │  Direction   │
                      │  Generation  │
                      └──────────────┘
                              ↓
                      ┌──────────────┐
                      │    Reports   │
                      │ (Daily/Week) │
                      └──────────────┘
                              ↓
                      ┌──────────────┐
                      │     User     │
                      │   Feedback   │
                      └──────────────┘
                              ↓
                      ┌──────────────┐
                      │   Profile    │
                      │    Update    │
                      └──────────────┘
                              ↓
                    (影响后续评分和推荐)
```

---

## 12. Storage Structure

```
data/
├── raw/                    # 原始抓取数据
│   ├── papers/
│   ├── blogs/
│   └── advisories/
├── artifacts/              # 结构化artifacts
│   └── {date}/
│       └── {artifact_id}.json
├── themes/                 # 主题数据
│   ├── core_themes.json   # 核心主题库
│   ├── candidate_themes.json  # 待确认主题
│   └── snapshots/
├── directions/             # 候选方向
│   └── {direction_id}.json
├── feedback/               # 用户反馈
│   └── {date}/
│       └── feedback_events.json
├── profile/                # 用户画像
│   ├── config.json        # 手动配置
│   └── snapshots/         # 自动生成快照
└── reports/                # 生成的报告
    ├── daily/
    └── weekly/
```

