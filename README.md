# Research Radar

面向安全领域博士研究选题的研究方向发现系统。

系统通过**双轨处理 + 统计空白检测**，从多层信息源中发现「工业界已在痛但学术界尚未充分解决」的研究空白，帮助用户找到高门槛、低竞争、有实际影响力的研究方向。

## 架构概览

```
                      Ingest
                 crawl → normalize → enrich(L1) → broad domain filter
                           |
             +-------------+-------------+
             |                           |
        ACADEMIC TRACK              INDUSTRY TRACK
        (T1 顶会 + T2 arXiv)       (T3 博客 + T4 未来快速源)
             |                           |
        L2 deep-analyze             signal-extract
             |                           |
        cluster → trend             demand signal 聚合
             |                           |
             +--- GAP DETECTOR ----------+
                       |
                DIRECTION SYNTHESIS → LANDSCAPE REPORT
```

## 数据源

| Tier | 来源 | 信号类型 | 状态 |
|------|------|---------|------|
| T1 | NDSS, S&P, CCS, USENIX Security | 学术覆盖 | ✅ |
| T2 | arXiv (cs.CR + cs.SE + cs.PL) | 趋势萌芽 | ✅ |
| T3 | Project Zero, PortSwigger, Cloudflare | 工业需求 | ✅ |
| T4 | 个人博客 / 公众号 | 快速热点 | 待接入 |

## 核心 Pipeline

| Pipeline | 作用 | 轨道 |
|----------|------|------|
| `deep-analyze` | 论文 L2 结构化分析 | 学术 |
| `cluster` | 论文按研究子领域聚类 | 学术 |
| `trend` | 趋势统计 + 方法论演进分析 | 学术 |
| `extract-signals` | 从博客提取需求信号 | 工业 |
| `detect-gaps` | 学术覆盖 vs 工业需求的交叉比对 | 交叉 |
| `synthesize` | 基于空白推导候选研究方向 | 综合 |

## 快速使用

```bash
# 环境
conda activate research-radar

# 首次设置
python -m src.cli profile seed-v2          # 加载宽泛 Profile
python -m src.cli migrate-tiers            # 迁移 tier 值

# 日常运行
python -m src.cli run --skip-crawl --provider anthropic --report-type daily

# 完整智能分析（每周）
python -m src.cli run --skip-crawl --full --provider anthropic

# 单步命令
python -m src.cli deep-analyze --provider anthropic
python -m src.cli extract-signals --provider anthropic
python -m src.cli cluster --provider anthropic
python -m src.cli trend --provider anthropic
python -m src.cli detect-gaps
python -m src.cli synthesize --provider anthropic
python -m src.cli report --type landscape
```

## 项目状态

- **测试**: 159 passed, 5 subtests passed
- **数据**: 3980 artifacts (论文 3925 + 博客 55)
- **v2 架构**: Phase A-D1 全部实现
- **待做**: live 验证、D2 反馈闭环、T4 源接入

## 设计文档

- `docs/design/01_architecture.md` — 架构与数据流
- `docs/design/03_scoring_strategy.md` — 分轨评分策略
- `docs/design/05_source_plan.md` — 数据源计划
- `docs/design/09_intelligence_layer.md` — 智能分析层（v2 双轨架构，核心设计）
- `docs/iteration_plan.md` — 迭代计划与进度

## 技术栈

Python 3.10+ / SQLAlchemy 2.0 / SQLite / Click CLI / Anthropic API (Haiku)
