# Live Run Report (2026-03-11)

## Scope

本次运行验证了以下链路：

- Anthropic-compatible 第三方 provider 配置
- `enrich` 全量执行
- `score` 全量执行
- `report` 日报 / 周报生成

---

## Environment

- Repository: `research-radar`
- Runtime: `conda run -n research-radar`
- Provider mode: Anthropic-compatible API
- Base URL: `https://node-hk.sssaicode.com/api/v1/messages`
- Models:
  - FAST: `claude-haiku-4-5-20251001`
  - STANDARD: `claude-sonnet-4-6`
  - PREMIUM: `claude-opus-4-6`

---

## Commands Executed

```bash
conda run -n research-radar python -m src.cli --verbose enrich --provider anthropic --artifact-id 1
screen -dmS rr-enrich zsh -lc 'cd /Users/jerry/Desktop/Research/research-radar && /opt/homebrew/anaconda3/envs/research-radar/bin/python -u -m src.cli enrich --provider anthropic >> /tmp/research_radar_enrich.log 2>&1'
conda run -n research-radar python -m src.cli --verbose enrich --provider anthropic --artifact-id 527
conda run -n research-radar python -m src.cli score
conda run -n research-radar python -m src.cli report --type daily --date 2026-03-10
conda run -n research-radar python -m src.cli report --type daily --date 2026-03-11
conda run -n research-radar python -m src.cli report --type weekly --date 2026-03-11
```

---

## Results

- Artifact corpus: `1168`
- Enrichment complete: `1168 / 1168`
- Scoring complete: `1168 / 1168`
- Generated reports:
  - `data/reports/daily/2026-03-10.md`
  - `data/reports/daily/2026-03-11.md`
  - `data/reports/weekly/2026-W11.md`

首轮 batch enrichment 的汇总日志为：

```text
Enrichment complete: 549 enriched, 618 skipped, 1 failed
```

其中：

- `618 skipped` 来自之前已经有摘要 / tags 的记录
- 唯一失败条目为 artifact `527`
- 补跑后 `pending_count = 0`

---

## Observations

### 1. Provider endpoint 必须使用完整路径

第三方文档里给出的根地址是给特定客户端自己拼 path 用的。本项目当前实现要求：

- Anthropic-compatible: 必须填完整 `.../api/v1/messages`
- 只填根路径 `.../api` 不可用

### 2. Full batch 适合后台执行

全量 enrichment 运行时间明显长于单条 smoke test，实际使用 `screen` 后台会话执行更稳定，日志写入到：

- `/tmp/research_radar_enrich.log`

### 3. 观察到吞吐波动，但日志中没有明确 429 / timeout

运行过程中单条完成速度有波动，但当前日志没有出现明确的 `429`、`rate limit` 或 `timeout` 文本。更保守的结论是：

- 第三方网关存在响应吞吐波动
- 现阶段不能仅根据现象断定为显式限流

### 4. 出现了真实的结构化输出漂移样本

artifact `527` 在首轮 enrichment 中返回了 fenced JSON，并且 `summary_l1` 内含未转义双引号，导致标准 `json.loads()` 失败。

已落地修复：

- 保留原有 fence stripping
- 新增 relaxed parser，允许从常见 malformed payload 中恢复 `summary_l1` 和 `tags`
- 补跑时命中了本地 cache，因此无需再次调用 provider

### 5. `score` 必须先于 `report`

一次手工并行执行中，`weekly report` 在 `score` 完成前运行，产生了“窗口内 artifact 无 `final_score`”的告警和无效输出。重新按顺序执行后恢复正常。

结论：

- 手工操作时不要并行跑 `score` 和 `report`
- `src.cli run` 的顺序定义是正确的

### 6. 当前评分在该语料上几乎没有区分度

本次 live 语料全部落成了：

- `papers = 1168`
- `blogs = 0`
- `advisories = 0`
- `created_at = 2026-03-10`

同时 P3.1 评分只使用 `recency + authority`。结果是：

- `1168` 条记录全部得到 `final_score = 1.0`
- 周报 Top 10 几乎退化为按插入顺序截断

这不是运行故障，但说明：

- 当前 Phase 1 评分在同质高质量论文集上缺少排序区分度
- 后续应优先引入 relevance / feedback / 更丰富的数据源

### 7. 日报日期需要按 UTC 理解

数据库中的 `created_at` 分布为：

- `2026-03-10`: `1168`

因此：

- `report --type daily --date 2026-03-10` 有内容
- `report --type daily --date 2026-03-11` 为空

这符合当前实现的 UTC 时间窗定义，不是 bug，但操作时容易误判。

---

## Review Focus

建议 review 时重点看这几项：

1. `src/pipelines/enrichment.py` 的 relaxed parser 是否接受
2. 是否要把 `report` 的日期说明直接加到 CLI help 或文档里
3. 是否要优先推进更有区分度的 scoring signal（relevance / feedback）
4. 是否要为 full batch 运行补一个正式的后台执行 / 断点续跑说明
