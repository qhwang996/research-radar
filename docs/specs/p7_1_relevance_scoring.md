# P7.1 Relevance Scoring - Implementation Spec

## 1. Goal

为每个 artifact 计算 relevance_score（0.0-1.0），衡量内容与用户研究兴趣的匹配度。这是当前评分系统最大的缺失：recency 和 authority 只能区分来源和时间，同一年同一会议的论文得分完全相同，没有任何个性化区分度。

完成后评分公式变为：

```text
final_score = recency x 0.4 + authority x 0.3 + relevance x 0.3
```

与设计文档 `03_scoring_strategy.md` 第 1 节一致。

---

## 2. Dependencies

- P0.1 数据模型（`Artifact.relevance_score` 字段已存在）
- P2.2 LLM 服务层（`LLMClient` + cache）
- P3.1 Scoring Engine（`CompositeStrategy`）

无新增外部依赖。

---

## 3. 分两步：keyword match + LLM relevance

### 3.1 Profile 初始化（前置任务）

数据库中当前没有 Profile 记录。需要创建一个 seed profile。

新增文件 `data/seed_profile.json`：

```json
{
  "profile_version": "v1-seed",
  "current_research_area": "Web应用安全与软件安全",
  "interests": [
    "Web漏洞检测",
    "渗透测试自动化",
    "Java安全",
    "反序列化漏洞",
    "供应链安全",
    "模糊测试",
    "程序分析",
    "漏洞挖掘"
  ],
  "preferred_topics": [
    "web-security",
    "vulnerability-detection",
    "fuzzing",
    "program-analysis",
    "binary-analysis",
    "supply-chain-security",
    "deserialization",
    "java-security",
    "penetration-testing",
    "exploit-development",
    "xss",
    "sql-injection",
    "csrf",
    "ssrf",
    "rce"
  ],
  "avoided_topics": [
    "cryptography-theory",
    "blockchain",
    "formal-verification",
    "privacy-policy",
    "usable-security-survey",
    "network-protocol-theory",
    "quantum-computing"
  ],
  "primary_goals": [
    "找到未来3-5年有潜力的安全研究方向",
    "关注对工业界有实际影响的研究",
    "关注有明确技术贡献的工作"
  ],
  "evaluation_criteria": {
    "must_have": "明确的技术贡献或新攻击面",
    "nice_to_have": "有原型实现或实际影响证据",
    "dealbreaker": "纯理论无应用场景"
  },
  "is_active": true
}
```

新增 CLI 子命令 `python -m src.cli profile seed` 读取此文件并写入数据库。如果已有 active profile 则跳过（幂等）。

### 3.2 Keyword Match（无 LLM 成本）

新增文件 `src/scoring/relevance.py`，实现 `RelevanceStrategy(BaseScoringStrategy)`。

keyword match 逻辑：

1. 从 `Profile` 中读取 `preferred_topics` 和 `avoided_topics`
2. 搜索范围：`artifact.title + artifact.abstract + artifact.summary_l1 + artifact.tags`（全部转小写，连字符和下划线统一为空格后匹配）
3. 计算方式：
   - 命中 1 个 `preferred_topic` -> 0.4
   - 命中 2 个 -> 0.6
   - 命中 3 个 -> 0.8
   - 命中 4 个及以上 -> 1.0
   - 未命中任何 -> 0.1（不是 0，留给 LLM 判断空间）
   - 如果命中任意 `avoided_topic` -> 得分 x 0.3（惩罚系数）
4. 如果 `profile` 为 `None`，返回 0.5（中性）

keyword match 阶段不调用 LLM，纯本地计算，无成本。

### 3.3 LLM Relevance（Phase 2.2，本任务暂不实现）

设计文档中描述的 LLM relevance scoring（让 LLM 评 1-5 分）暂不在本任务范围。原因：

- keyword match + tags 已能提供可用的区分度（tags 已由 enrichment 生成）
- 1168 条全部调 LLM 成本较高，应先验证 keyword match 效果
- 后续可作为独立任务追加

在代码中预留 `llm_relevance_score` 的合并接口，但本任务只实现 keyword match 部分。

---

## 4. CompositeStrategy 更新

修改 `src/scoring/composite.py`：

1. 默认权重改为 `recency=0.4, authority=0.3, relevance=0.3`
2. 新增 `relevance_strategy` 参数（默认 `RelevanceStrategy()`）
3. `calculate_breakdown` 返回新增 `relevance_score` 字段
4. `formula` 字段更新为 `"final_score = recency * 0.4 + authority * 0.3 + relevance * 0.3"`
5. `version` 字段更新为 `"phase2-v1"`

修改 `src/scoring/engine.py`：

- `_score_and_persist` 中新增 `artifact.relevance_score = float(breakdown["relevance_score"])`

---

## 5. CLI 命令

### 5.1 `python -m src.cli profile seed`

新增文件 `src/cli/profile.py`：

- 读取 `data/seed_profile.json`
- 如果数据库已有 active profile 则打印 `"Active profile already exists, skipping."` 并退出
- 否则写入数据库并打印 `"Seeded profile: {profile_version}"`

在 `src/cli/main.py` 中注册 `profile` 命令组。

### 5.2 `python -m src.cli profile show`

打印当前 active profile 的 JSON 信息（`current_research_area`, `interests`, `preferred_topics`, `avoided_topics`）。

---

## 6. 文件清单

新增：

- `src/scoring/relevance.py` - `RelevanceStrategy`
- `src/cli/profile.py` - profile `seed` / `show` 命令
- `data/seed_profile.json` - 初始用户画像
- `tests/scoring/test_relevance.py` - relevance 单元测试
- `tests/cli/test_profile.py` - profile CLI 测试

修改：

- `src/scoring/composite.py` - 三因子权重
- `src/scoring/engine.py` - 写入 `relevance_score`
- `src/cli/main.py` - 注册 `profile` 命令

---

## 7. 测试要求

`test_relevance.py`

1. `test_no_profile_returns_neutral` - `profile=None` 时返回 0.5
2. `test_single_keyword_match` - `title` 命中 1 个 `preferred_topic` -> 0.4
3. `test_multiple_keyword_match` - `title+abstract` 命中 3 个 -> 0.8
4. `test_four_plus_keywords_caps_at_one` - 命中 4+ 个 -> 1.0
5. `test_no_match_returns_floor` - 无命中 -> 0.1
6. `test_avoided_topic_penalty` - 命中 preferred 但也命中 avoided -> 得分打 0.3 折扣
7. `test_tags_contribute_to_match` - `artifact.tags` 中的关键词也参与匹配
8. `test_summary_l1_contributes_to_match` - `summary_l1` 中的关键词参与匹配

`test_profile.py`

1. `test_seed_creates_profile` - `seed` 命令成功创建 profile
2. `test_seed_is_idempotent` - 已有 active profile 时 `seed` 跳过

现有测试更新

- `tests/scoring/test_scoring_engine.py` 中 composite 相关测试需要更新权重和 breakdown 字段（新增 `relevance_score`）

---

## 8. 验收标准

1. `conda run -n research-radar python -m pytest -v` 全部通过
2. `conda run -n research-radar python -m src.cli profile seed` 成功创建 profile
3. `conda run -n research-radar python -m src.cli score` 重新评分后，同一年的论文 `relevance_score` 出现不同值
4. `conda run -n research-radar python -m src.cli report --type daily --date 2026-03-10` 日报中 artifact 排序有明显区分度（不再全部 1.0）

---

## 9. 不做的事

- LLM relevance scoring（后续独立任务）
- Feedback multiplier 接入（P5.2）
- Profile 自动学习/更新（Phase 3）
- 批量 keyword 扩展（如同义词/上下位词）
