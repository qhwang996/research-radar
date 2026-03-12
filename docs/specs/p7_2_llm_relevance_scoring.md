# P7.2 LLM Relevance Scoring - Implementation Spec

## 1. Goal

用 LLM 为每条 artifact 评估研究相关度（1-5 分），弥补 keyword match 无法理解语义的缺陷。例如 keyword match 对 "web fuzzing" 和 "sensor fuzzing" 都命中 "fuzzing"，但 LLM 能理解前者与用户的 web 安全兴趣更相关。

完成后 `relevance_score` 变为：

```text
relevance_score = keyword_match x 0.4 + llm_relevance x 0.6
```

这个合并公式已在 P7.1 的 `_merge_relevance_scores` 中实现，本任务只需要让 `_calculate_llm_relevance_score` 返回真实值。

---

## 2. Dependencies

- P7.1 `RelevanceStrategy`（已有合并接口）
- P2.2 `LLMClient`（cache + retry）
- Profile seed 数据（已通过 `profile seed` 创建）

无新增外部依赖。

---

## 3. 架构决策：独立 pipeline，不在 scoring 循环里调 LLM

LLM relevance 评分不应该在 `RelevanceStrategy.calculate_score()` 内直接调用 LLM，那样每次 `score` 命令都会触发 1168 次 API 调用。

方案：新增一个独立的 `LLMRelevancePipeline`，预计算 LLM relevance 分数并存入 `artifact.score_breakdown["llm_relevance_score"]`。`RelevanceStrategy` 在 scoring 时从 `score_breakdown` 读取已缓存的 LLM 分数。

流程变为：

```text
profile seed -> enrich -> llm-relevance -> score -> report
```

---

## 4. 实现细节

### 4.1 `LLMRelevancePipeline`

新增文件 `src/pipelines/llm_relevance.py`：

```python
class LLMRelevancePipeline(BasePipeline):
    """Pre-compute LLM relevance scores for artifacts."""
```

核心逻辑：

1. 读取所有 active artifact
2. 跳过已有 `score_breakdown.get("llm_relevance_score")` 且非 `None` 的条目（幂等）
3. 对每条 artifact，用 LLM 生成 1-5 分评估
4. 将 LLM 原始分数（1-5）映射为 0.0-1.0：`{1: 0.2, 2: 0.4, 3: 0.6, 4: 0.8, 5: 1.0}`
5. 将结果存入 `artifact.score_breakdown["llm_relevance_score"] = mapped_score`
6. 单条失败不阻塞整批，记录 error 继续
7. 使用 `LLMClient` 的文件缓存，`cache_key` 格式：`relevance_v1_{artifact.canonical_id}`

### 4.2 Prompt

新增文件 `prompts/relevance_score.md`：

```text
你正在为一位安全领域博士研究生评估论文的研究相关度。

用户研究方向：{{research_area}}
核心兴趣：{{interests}}
偏好主题：{{preferred_topics}}
回避主题：{{avoided_topics}}

请评估以下论文与用户研究方向的相关度，打分 1-5：

5 = 直接相关：论文主题是用户核心兴趣（如 web 漏洞检测、Java 反序列化、web fuzzing）
4 = 高度相关：论文方法或场景与用户兴趣密切相关（如 web 场景的程序分析）
3 = 一般相关：安全领域但非用户核心方向（如通用 fuzzing、网络协议安全）
2 = 弱相关：安全领域但与用户方向较远（如硬件安全、传感器安全、侧信道）
1 = 不相关：与用户研究方向无关（如密码学理论、区块链、隐私政策调研）

论文信息：
标题：{{title}}
来源：{{source_name}} ({{source_tier}})
摘要：{{summary_l1}}
标签：{{tags}}

请只返回一个 JSON：
{"score": 数字, "reason": "一句话理由"}
```

### 4.3 `RelevanceStrategy` 修改

修改 `src/scoring/relevance.py` 的 `_calculate_llm_relevance_score`：

- 不再返回 `None`
- 从 `artifact.score_breakdown` 中读取 `llm_relevance_score`
- 如果不存在（pipeline 未跑过），仍返回 `None`（降级为纯 keyword match）

```python
def _calculate_llm_relevance_score(self, artifact: Artifact, profile: Profile) -> float | None:
    if not artifact.score_breakdown:
        return None
    llm_score = artifact.score_breakdown.get("llm_relevance_score")
    if llm_score is None:
        return None
    return float(llm_score)
```

这样 scoring 循环里不调 LLM，纯内存读取。

### 4.4 CLI 命令

新增子命令 `python -m src.cli llm-relevance`：

在 `src/cli/process.py` 中新增：

- `--provider` 参数（默认 `anthropic`）
- `--artifact-id` 可选，指定单条处理
- 使用 `STANDARD` tier

同时更新 `run` 命令，在 `enrich` 和 `score` 之间加入 `llm-relevance` 步骤。

---

## 5. 文件清单

新增：

- `src/pipelines/llm_relevance.py` - `LLMRelevancePipeline`
- `prompts/relevance_score.md` - LLM relevance prompt
- `tests/pipelines/test_llm_relevance.py` - pipeline 单元测试

修改：

- `src/scoring/relevance.py` - `_calculate_llm_relevance_score` 读取预计算结果
- `src/cli/process.py` - 新增 `llm-relevance` 命令，更新 `run` 命令
- `src/cli/main.py` - 注册新命令（如果需要）

---

## 6. 测试要求

`test_llm_relevance.py`

1. `test_pipeline_stores_llm_relevance_in_breakdown` - mock LLM 返回 `{"score": 4, "reason": "..."}`，断言 `artifact.score_breakdown["llm_relevance_score"] == 0.8`
2. `test_pipeline_skips_already_scored` - 已有 `llm_relevance_score` 的 artifact 不重复调用 LLM
3. `test_pipeline_continues_on_single_failure` - 单条 LLM 失败不阻塞其余
4. `test_score_mapping` - 验证 `1->0.2, 2->0.4, 3->0.6, 4->0.8, 5->1.0` 映射

`test_relevance.py` 更新

5. `test_llm_relevance_score_read_from_breakdown` - `artifact.score_breakdown` 中有 `llm_relevance_score` 时，`relevance_score` 应为 `keyword x 0.4 + llm x 0.6`
6. `test_llm_relevance_score_missing_falls_back_to_keyword_only` - `score_breakdown` 中无 `llm_relevance_score` 时，`relevance_score = keyword_match_score`

---

## 7. 验收标准

1. `conda run -n research-radar python -m pytest -v` 全部通过
2. `conda run -n research-radar python -m src.cli llm-relevance --provider anthropic` 对所有 artifact 生成 LLM relevance 分数
3. `conda run -n research-radar python -m src.cli score` 重新评分后，同一年同一会议的论文出现不同 `final_score`
4. web 安全直接相关论文（XSS、SQL injection、web fuzzing）排名高于泛安全论文（binary fuzzing、sensor fuzzing）

---

## 8. 不做的事

- 批量 prompt 合并（逐条调用，依赖文件缓存避免重复）
- LLM 分数自动更新（profile 变化后需手动重跑）
- `reason` 字段展示在报告中（存在 cache 中供调试，暂不展示）
