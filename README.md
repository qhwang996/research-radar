# Research Radar

面向安全科研的前沿情报收集、分层消费与周期总结系统。

研究方向发现仍保留，但作为周 / 月 / 季度层的上层输出，而不是底层唯一目标。

> 当前仓库状态、优先级和真实行为以 [`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md) 为唯一入口。README 只提供稳定定位，不维护分散的历史状态数字。

## 项目定位

Research Radar 的基线不是“只给一个研究方向”，而是先把安全科研相关信息稳定拉进来、分层处理、再按周期沉淀为低维护输出。

- Markdown-first
- CLI-first
- automation-first
- low-maintenance first
- rerunnable / idempotent first

核心链路：

```text
collect -> normalize -> enrich/filter -> score -> triage -> periodic synthesis
```

其中 `triage` 负责把内容分成 `read_original / detailed_summary / one_line / delegate_to_agent / archive`，`periodic synthesis` 负责把日常情报沉淀为周 / 月 / 季度层总结。

## 用户问题

这个系统要解决的不是“今天有没有一个新点子”，而是持续回答下面几类问题：

- `daily`: 今天什么值得注意，哪些该亲读，哪些只看一句话，哪些应该交给 agent 代读。
- `weekly`: 这周 academic frontier 是什么，industry signal 是什么，哪些 gap 值得继续跟。
- `monthly`: 哪些主题在重复出现，哪些 source 和 delegate 真正节省了时间。
- `quarterly`: 哪些方向值得进入研究路线图，哪些 source 应该保留、扩展或淘汰。

## 核心架构

```text
collect -> normalize -> enrich/filter -> score -> triage
        -> daily consumption
        -> weekly synthesis
        -> monthly consolidation
        -> quarterly strategy review
```

```text
                      ingest
                 crawl -> normalize -> enrich
                           |
             +-------------+-------------+
             |                           |
        academic track              industry track
        (T1 + T2)                   (T3 + T4)
             |                           |
        deep-analyze                extract-signals
        cluster -> trend            demand aggregation
             |                           |
             +-------- gap detector -----+
                           |
                    direction synthesis
                           |
                    periodic reports
```

`gap detector` 和 `direction synthesis` 仍然是核心能力，但它们现在属于周期总结层，而不是整个系统唯一的底层目的。

## 双轨原则

- academic 与 industry 分轨处理，不做一个总排行。
- academic 轨承载 T1 顶会和 T2 arXiv，重点是学术覆盖、主题聚类和趋势。
- industry 轨承载 T3 研究博客和未来的 T4 个人源，重点是需求信号和现实痛点。
- 研究空白来自两条轨道的交叉比对，而不是把所有内容拍平成一个列表。

## 报告体系

- `daily`: 5-10 分钟可读，面向当天消费决策。
- `weekly`: 主周报，面向 academic frontier / industry signals / cross-track gaps。
- `landscape`: 当前保留的兼容输出，可视为 weekly 的战略版或兼容别名。
- `monthly`: 面向稳定主题、阅读 ROI、delegate ROI、source performance。
- `quarterly`: 面向研究路线图、方向升级、source 保留/淘汰建议。

当前哪些报告已经实现、哪些仍在 backlog，请直接看 [`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md) 和 [`docs/CODEX_BACKLOG.md`](docs/CODEX_BACKLOG.md)。

## 核心 Source Tiers

| Tier | 枚举值 | 轨道 | 示例 | 作用 |
|------|--------|------|------|------|
| T1 | `t1-conference` | academic | NDSS, S&P, CCS, USENIX Security | 高权威学术覆盖 |
| T2 | `t2-arxiv` | academic | arXiv (`cs.CR`, `cs.SE`, `cs.PL`) | 趋势萌芽与新方向 |
| T3 | `t3-research-blog` | industry | Project Zero, PortSwigger, Cloudflare | 工业需求信号 |
| T4 | `t4-personal` | industry | 用户指定个人/公司博客 | 快速热点与补充信号 |

## 当前状态

仓库已经具备 crawl / normalize / enrich / llm-relevance / score / report 的基线能力，也已经引入双轨架构、gap detector 和 direction synthesis。

但 README 不再维护易漂移的测试数、数据量和阶段数字。最新状态、已确认漂移和推荐起手工单统一收敛到 [`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md)。

## 快速开始

```bash
# 环境
conda activate research-radar

# 首次设置
python -m src.cli profile seed-v2
python -m src.cli migrate-tiers

# 日常运行：生成日报
python -m src.cli run --skip-crawl --provider anthropic --report-type daily

# 每周完整链路：跑 intelligence analysis，并输出 landscape
python -m src.cli run --skip-crawl --full --provider anthropic

# 独立命令
python -m src.cli deep-analyze --provider anthropic
python -m src.cli extract-signals --provider anthropic
python -m src.cli cluster --provider anthropic
python -m src.cli trend --provider anthropic
python -m src.cli detect-gaps
python -m src.cli synthesize --provider anthropic
python -m src.cli report --type weekly
python -m src.cli report --type landscape
```

## 文档入口

- [`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md): 唯一主入口，先看这个。
- [`AGENTS.md`](AGENTS.md): 持续开发边界、默认偏好和任务流程。
- [`docs/TARGET_SYSTEM.md`](docs/TARGET_SYSTEM.md): 目标链路与分层消费定位。
- [`docs/TRIAGE_POLICY.md`](docs/TRIAGE_POLICY.md): triage bucket 定义与分流规则。
- [`docs/REPORT_POLICY.md`](docs/REPORT_POLICY.md): 日 / 周 / 月 / 季报表策略。
- [`docs/CODEX_BACKLOG.md`](docs/CODEX_BACKLOG.md): 当前连续开发队列。
- [`docs/design/01_architecture.md`](docs/design/01_architecture.md): 架构与数据流。
- [`docs/design/03_scoring_strategy.md`](docs/design/03_scoring_strategy.md): 分轨评分策略。
- [`docs/design/05_source_plan.md`](docs/design/05_source_plan.md): source tier 与接入计划。
- [`docs/design/09_intelligence_layer.md`](docs/design/09_intelligence_layer.md): 双轨 + gap detector + direction synthesis 设计。

## 历史说明

这个项目最初更像“安全领域博士研究方向发现器”。这部分能力没有删除，但已经被上移到周 / 月 / 季度层，作为更大系统中的一个高层产物。

换句话说，现在的底层系统首先服务于情报收集、分层消费和周期总结；研究方向发现是这些能力稳定运行之后的上层综合输出。
