# Idempotency and Replay

## 1. Why this matters

本系统是一个长期运行、频繁改规则、需要多次重跑的研究方向收敛系统。

因此必须满足：

- 重复执行不会污染数据
- 宕机后可以恢复
- 历史结果可以重现
- 新旧规则结果可以比较
- 外部副作用可控

---

## 2. Core Rules

### Rule 1: Persist before derive
先保存原始输入，再做派生处理。

### Rule 2: Append events, snapshot states
反馈等行为类数据 append-only；画像、主题、候选方向等状态类数据用 snapshot。

### Rule 3: Every stage has a stable key
每个阶段都必须有唯一键或幂等键。

### Rule 4: Replay should be safe
相同输入在 replay 时，不应产生重复 artifact、重复报告或重复反馈事件。

---

## 3. Stage-by-stage Idempotency

### 3.1 Ingestion / raw_fetch

#### Input
- source config
- fetched content

#### Output
- raw_fetch

#### Idempotency Key
建议：
- `source_id + content_hash`
或
- `source_id + normalized_url + content_hash`

#### Replay Behavior
- 若原始内容已存在，则跳过或标记 duplicate
- 不覆盖已有 raw 记录
- 新抓取记录可继续保留，便于分析 source 波动

---

### 3.2 Normalization / artifact

#### Input
- raw_fetch
- parse rules
- normalization version

#### Output
- artifact

#### Idempotency Key
- `canonical_id`

#### Replay Behavior
- 若 canonical_id 已存在，则 upsert 或建立 raw->artifact 关联
- artifact 的结构升级不应破坏旧记录可读性
- normalize_version 应显式记录

---

### 3.3 Deduplication

#### Input
- artifacts
- dedup rules

#### Output
- deduped artifact view / mapping

#### Idempotency Key
- `canonical_id`
- optional alias mapping keys

#### Replay Behavior
- dedup 规则变化后允许重算
- 不直接删除底层 artifact
- 尽量以映射或视图表达“合并”结果

---

### 3.4 Theme Snapshot

#### Input
- artifact set
- scoring rules
- period window

#### Output
- theme_snapshot

#### Idempotency Key
- `run_id + theme_key`
或
- `period_key + generation_version + theme_key`

#### Replay Behavior
- 同一 run 内相同 theme_key 不重复生成
- 新规则产生新 snapshot，不覆盖旧 snapshot

---

### 3.5 Candidate Direction Snapshot

#### Input
- theme snapshots
- ranking rules
- latest profile snapshot

#### Output
- candidate_direction_snapshot

#### Idempotency Key
- `week_id + generation_version + rank`
或独立 `candidate_id`

#### Replay Behavior
- 同一 generation_version 下不重复写入同 rank 对象
- 规则变化应产生新的 generation_version

---

### 3.6 Reporting

#### Input
- candidate directions
- report template
- report generation version

#### Output
- report file
- report_log

#### Idempotency Key
- `report_type + period_key + generation_version`

#### Replay Behavior
- 同一键值已存在时不重复生成
- 若模板变化但逻辑版本不变，可单独提升 generation_version

---

### 3.7 Feedback Event

#### Input
- user feedback

#### Output
- feedback_event

#### Idempotency Key
- `event_id`

#### Replay Behavior
- feedback event append-only
- 不覆盖既有反馈
- 若需要修正，新增 correction event，而不是修改旧事件

---

### 3.8 Profile Snapshot

#### Input
- feedback event range
- profile extraction logic version

#### Output
- profile_snapshot

#### Idempotency Key
- `profile_version`

#### Replay Behavior
- 新逻辑生成新 profile_version
- 不覆盖旧 profile snapshot
- 排序器默认读取最新 profile_version

---

## 4. Snapshot vs Event

### Append-only Events
适合：

- feedback_event
- source ingest logs
- manual annotations

### Snapshots
适合：

- theme_snapshot
- candidate_direction_snapshot
- profile_snapshot
- report outputs

---

## 5. Replay Scenarios

### Scenario A: parser improved
当 parser 升级时：

1. 保留旧 raw_fetch
2. 使用新 normalize_version 重跑 normalization
3. 比较新旧 artifact 差异

### Scenario B: scoring changed
当 scoring 规则变化时：

1. 保留旧 artifact
2. 重算 theme_snapshot
3. 重算 candidate_direction_snapshot
4. 生成新的 weekly report version

### Scenario C: profile logic changed
当从 feedback 提取偏好的逻辑变化时：

1. 保留 feedback_event
2. 生成新的 profile_snapshot
3. 重跑 shortlist ranking

---

## 6. Anti-patterns to avoid

不要这样做：

- 用“更新覆盖”替代版本化
- 在一个步骤里同时做解析、排序、写报告、写反馈
- 删除旧快照来节省空间
- 用隐式内存状态代表真实系统状态
- 没有唯一键就直接 insert

---

## 7. Practical MVP Guidance

首版最小要求：

- raw_fetch 有 content_hash
- artifact 有 canonical_id
- report_log 有 report_id
- feedback_event 有 event_id
- theme / candidate / profile 都作为 snapshot 保存
- replay 时通过 generation_version 区分新旧结果

做到这些，系统就已经具备长期演进的基础。