# RUNBOOK

## 1. 目标

这是面向“低管理成本”的操作说明。
默认只保留最少、稳定、可重跑的操作路径。

## 2. 运行前提

### 2.1 环境
- Python 3.10+
- 可用数据库（默认 SQLite）
- 有效的 LLM provider 凭证
- 网络可访问目标 source

### 2.2 首次初始化
```bash
conda activate research-radar
python -m src.cli profile seed-v2
python -m src.cli migrate-tiers
```

## 3. 当前可用命令（基于现有仓库）

### 3.1 生成日报（不抓取）
```bash
python -m src.cli run --skip-crawl --provider openai --report-type daily
```

### 3.2 生成完整智能分析周报/landscape（不抓取）
```bash
python -m src.cli run --skip-crawl --full --provider anthropic --report-type landscape
```

### 3.3 单独执行关键步骤
```bash
python -m src.cli normalize
python -m src.cli enrich --provider openai
python -m src.cli llm-relevance --provider gemini
python -m src.cli score
python -m src.cli deep-analyze --provider anthropic
python -m src.cli extract-signals --provider anthropic
python -m src.cli cluster --provider anthropic
python -m src.cli trend --provider anthropic
python -m src.cli detect-gaps
python -m src.cli synthesize --provider anthropic
python -m src.cli report --type daily
python -m src.cli report --type weekly
python -m src.cli report --type landscape
```

## 4. 推荐运行节奏

### Daily
目标：产出日报。
当前最稳妥方式：
```bash
python -m src.cli run --skip-crawl --provider openai --report-type daily
```

### Weekly
目标：产出 full intelligence 输出。
当前最稳妥方式：
```bash
python -m src.cli run --skip-crawl --full --provider anthropic --report-type landscape
```

### Monthly / Quarterly
当前仍是目标能力。
在实现对应 report generator 前，不要伪造“月报/季报”操作路径。

## 5. 安全重跑原则

如果怀疑某一步失败，可优先直接重跑整条链，而不是手改数据库。

原因：
- RawFetch + content_hash
- canonical_id upsert
- append-only feedback
- 报表可重生成

除非明确要做数据修复，不要直接改 SQLite 内容。

## 6. 常见故障与处理

### 6.1 crawl 失败
现象：
- 站点模板变了
- 网络失败
- 只有部分 source 成功

处理：
- 先记录失败 source
- 不要阻塞整个仓库重定位工作
- 若是 parser 漂移，开一个独立 source 修复工单
- 若只是临时网络失败，保留重跑

### 6.2 enrich / deep-analyze / llm-relevance 失败
现象：
- LLM provider 失败
- timeout
- 单条内容解析失败

处理：
- 优先利用现有 parallel + isolated failure 机制
- 检查 provider 配置
- 保持单条失败不阻塞全批次
- 不要为单条失败回滚整次 run

### 6.3 report 为空
先检查：
- 该周期是否有新增内容
- 是否被 read 过滤
- 是否时间窗口问题
- 是否 `created_at` 过滤导致 update-only 内容未进报告

如果确认是策略问题，改 `REPORT_POLICY` + generator；不要先手改数据。

### 6.4 feedback 看起来没有“生效”
这是已知现状：
- 当前 feedback 已采集
- 但尚未成为排序/triage 回流的强信号

解决方式：
- 走 `RR-007`，而不是临时 patch 某个报表排序

## 7. 与自动化集成的建议

自动化一定要分层：

- daily automation：只跑日报链
- weekly automation：跑 full intelligence
- monthly / quarterly automation：在对应 report generator 落地后再加

不要让一个超长任务同时负责所有周期输出。

## 8. 操作红线

- 不要手工删 report 来“假装刷新状态”
- 不要手工改 artifact score 纠偏
- 不要在生产数据上做试验性 schema 改动
- 不要在未更新 `CURRENT_STATUS.md` 的情况下 merge 行为变化

## 9. 每次变更操作路径后必须同步更新

- `docs/CURRENT_STATUS.md`
- `docs/RUNBOOK.md`
- `README.md`
