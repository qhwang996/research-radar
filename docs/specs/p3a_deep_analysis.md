# P3a L2 Deep Analysis Pipeline - Implementation Spec

## 1. Goal

对高相关论文（relevance_score >= 0.6）生成结构化深度分析，填充 `Artifact.summary_l2`。这是智能分析层（Phase 3）的第一步，为后续主题聚类和方向综合提供原材料。

当前 enrichment 只生成一句话摘要（summary_l1，≤160 字符）+ 关键词 tags。L2 分析需要深入到：这篇论文解决什么问题、用什么方法、有什么贡献、有什么局限、还有什么开放问题。

完成后，`summary_l2` 存储一个 JSON 字符串，结构如下：

```json
{
  "research_problem": "这篇论文要解决什么问题",
  "motivation": "为什么这个问题重要/现有方案的不足",
  "methodology": "核心方法/技术路线",
  "core_contributions": ["贡献1", "贡献2"],
  "limitations": ["局限1", "局限2"],
  "open_questions": ["可进一步研究的问题1", "问题2"],
  "related_concepts": ["相关概念/技术1", "技术2"]
}
```

---

## 2. Dependencies

- `Artifact.summary_l2` 字段已存在（Text, nullable），直接使用
- `EnrichmentPipeline` / `LLMRelevancePipeline` 作为实现模式参考
- `LLMClient`（STANDARD tier, cache + retry）
- `ProfileRepository.get_latest_active()` 提供用户研究上下文

无新增外部依赖。无 schema 变更。

---

## 3. 实现细节

### 3.1 `DeepAnalysisPipeline`

新增文件 `src/pipelines/deep_analysis.py`。

**完全复用 `EnrichmentPipeline` 的架构模式**，包括：
- `BasePipeline` 子类
- `ThreadPoolExecutor` 并行（`max_workers=4`，STANDARD 调用较慢）
- thread-local `LLMClient` 复制（`_get_worker_llm_client`）
- `ProfileContext` 快照传递到 worker 线程
- `ArtifactTask` dataclass 用于任务分发
- 单条失败不阻塞整批，记录 error 继续
- JSON 解析容错（`_strip_code_fences` + relaxed fallback）

```python
class DeepAnalysisPipeline(BasePipeline):
    """Generate structured L2 deep analysis for high-relevance papers."""
```

**核心参数**：

| 参数 | 值 | 说明 |
|------|-----|------|
| model_tier | `ModelTier.STANDARD` | 代码保留 tier 分层，运行时通过环境变量映射到 haiku |
| max_tokens | 1500 | 结构化 JSON 输出较长 |
| temperature | 0.3 | 保持确定性 |
| cache_key | `deep_analysis_{analysis_version}_{canonical_id}` | 版本化缓存 |
| max_workers | 4 | 控制并发，STANDARD 调用较慢 |
| analysis_version | `"v1"` | 版本号，变更时强制重分析 |

**筛选条件**（在 `_needs_analysis` 方法中）：

```python
def _needs_analysis(self, artifact: Artifact) -> bool:
    return (
        artifact.status == ArtifactStatus.ACTIVE
        and artifact.source_type == SourceType.PAPERS
        and (artifact.relevance_score is not None and artifact.relevance_score >= self.min_relevance)
        and not (artifact.summary_l2 or "").strip()
    )
```

默认 `min_relevance = 0.6`，可通过构造函数参数覆盖。

**process() 签名**：

```python
def process(self, input_data: Any) -> list[Artifact]:
```

`input_data` 支持：
- `None` → 分析所有符合条件的 artifact
- `int` → 分析指定 ID（忽略 relevance 阈值，强制分析）
- `list[int]` → 批量指定

**数据写入**：

```python
artifact.summary_l2 = json.dumps(payload_dict, ensure_ascii=False)
artifact_repository.save(artifact)
```

### 3.2 Prompt

新增文件 `prompts/deep_analysis.md`：

```
你是一位安全研究领域的论文分析专家。请对以下论文进行结构化深度分析。

用户研究方向：{{research_area}}
核心兴趣：{{interests}}

论文信息：
标题：{{title}}
来源：{{source_name}} ({{source_tier}})，{{year}} 年
作者：{{authors}}
摘要：{{abstract}}
一句话总结：{{summary_l1}}
标签：{{tags}}

请返回一个 JSON，不要加 Markdown 代码块，不要额外解释：

{
  "research_problem": "这篇论文要解决的核心问题（1-2 句话）",
  "motivation": "为什么这个问题重要，现有方案有什么不足（1-2 句话）",
  "methodology": "核心方法或技术路线（1-2 句话）",
  "core_contributions": ["主要贡献1", "主要贡献2"],
  "limitations": ["局限性1", "局限性2"],
  "open_questions": ["论文提出或暗示的待解决问题1", "问题2"],
  "related_concepts": ["相关的核心概念或技术1", "技术2"]
}

要求：
- 每个字段必须有实质内容，不要泛泛而谈
- limitations 和 open_questions 对后续研究选题最重要，请尽量具体
- core_contributions 列出 2-3 个，limitations 列出 1-3 个，open_questions 列出 1-3 个
- related_concepts 列出 3-5 个核心概念/技术，用于后续主题聚类
- 如果论文摘要信息有限，基于标题和来源做合理推断，但在 limitations 中注明信息不足
- 使用中文
```

**Prompt 中的占位符**需在 `_build_prompt` 方法中替换：

| 占位符 | 来源 |
|--------|------|
| `{{research_area}}` | `profile.current_research_area` |
| `{{interests}}` | `', '.join(profile.interests)` |
| `{{title}}` | `artifact.title` |
| `{{source_name}}` | `artifact.source_name` |
| `{{source_tier}}` | `artifact.source_tier` |
| `{{year}}` | `artifact.year` |
| `{{authors}}` | `', '.join(artifact.authors)` |
| `{{abstract}}` | `artifact.abstract or 'N/A'` |
| `{{summary_l1}}` | `artifact.summary_l1 or 'N/A'` |
| `{{tags}}` | `', '.join(artifact.tags)` |

### 3.3 JSON 解析

新增 `DeepAnalysisPayload` dataclass：

```python
@dataclass(slots=True)
class DeepAnalysisPayload:
    research_problem: str
    motivation: str
    methodology: str
    core_contributions: list[str]
    limitations: list[str]
    open_questions: list[str]
    related_concepts: list[str]
```

解析逻辑 `_parse_analysis_response`：

1. `_strip_code_fences`（复用 enrichment 的实现，或抽到共享工具）
2. `json.loads`，失败则尝试 `_extract_json_payload`（从 `LLMRelevancePipeline` 复用的 JSON 提取方法）
3. 验证 7 个必需字段都存在且非空
4. `core_contributions` / `limitations` / `open_questions` / `related_concepts` 必须是 `list[str]`
5. 字符串字段做 whitespace 清理
6. 缺失字段不 raise，而是用空字符串/空列表降级，记录 warning

### 3.4 CLI 命令

在 `src/cli/process.py` 新增：

```python
@main.command("deep-analyze")
@click.option("--provider", default="anthropic", type=click.Choice(["openai", "anthropic", "gemini"]))
@click.option("--artifact-id", default=None, type=int, help="只分析指定 artifact")
@click.option("--workers", default=4, type=int, help="并行 worker 数")
@click.option("--min-relevance", default=0.6, type=float, help="最低 relevance 阈值")
@pass_app_context
@handle_command_errors
def deep_analyze_command(ctx, provider, artifact_id, workers, min_relevance):
    """对高相关论文生成 L2 深度分析。"""
```

在 `src/cli/main.py` 注册命令（如果需要）。

同时更新 `run` 命令：在现有 `llm-relevance` 和 `score` 之间**不**插入 deep-analyze（因为 deep-analyze 依赖 relevance_score，应在 score 之后）。但考虑到 `run --full` 的设计（P3e 才实现），本阶段 `run` 命令**不修改**，deep-analyze 只作为独立命令。

---

## 4. 文件清单

**新增**：

| 文件 | 说明 |
|------|------|
| `src/pipelines/deep_analysis.py` | `DeepAnalysisPipeline` |
| `prompts/deep_analysis.md` | L2 深度分析 prompt 模板 |
| `tests/pipelines/test_deep_analysis.py` | pipeline 单元测试 |

**修改**：

| 文件 | 改动 |
|------|------|
| `src/cli/process.py` | 新增 `deep-analyze` 命令 |
| `src/cli/main.py` | 注册 `deep_analyze_command`（如 process.py 中的命令需要手动注册） |

**不修改**：
- `Artifact` 模型（`summary_l2` 已存在）
- `run` 命令（`--full` 在 P3e 实现）
- scoring / reporting 代码

---

## 5. 测试要求

`tests/pipelines/test_deep_analysis.py`：

使用 `StubLLMClient`（复用 enrichment 测试中的 mock 模式），创建隔离的 SQLite 数据库。

1. **`test_pipeline_stores_l2_analysis`** — mock LLM 返回完整 JSON，断言 `artifact.summary_l2` 非空，JSON 可解析，7 个字段都存在
2. **`test_pipeline_skips_already_analyzed`** — 已有 `summary_l2` 的 artifact 不重复调用 LLM
3. **`test_pipeline_skips_low_relevance`** — `relevance_score < 0.6` 的 artifact 被跳过
4. **`test_pipeline_skips_non_papers`** — `source_type == BLOGS` 的 artifact 被跳过
5. **`test_pipeline_continues_on_single_failure`** — 3 条 artifact，第 2 条 LLM 返回垃圾，其余正常完成
6. **`test_pipeline_forced_by_artifact_id`** — 通过 `input_data=artifact_id` 直接指定时，忽略 relevance 阈值
7. **`test_parse_response_with_code_fences`** — LLM 返回 ````json\n{...}\n```` 格式时仍能正确解析
8. **`test_parse_response_missing_fields_degrades`** — 缺少 `limitations` 字段时降级为空列表，不 raise

CLI 测试（在现有 CLI 测试文件中追加或新建）：

9. **`test_deep_analyze_command_runs`** — `CliRunner` 调用 `deep-analyze` 命令，mock LLM，验证正常退出

---

## 6. 验收标准

1. `conda run -n research-radar python -m pytest tests/pipelines/test_deep_analysis.py -v` 全部通过
2. `conda run -n research-radar python -m src.cli deep-analyze --provider anthropic --artifact-id <id>` 对单条 artifact 生成 L2 分析，`summary_l2` 非空且 JSON 可解析
3. `conda run -n research-radar python -m src.cli deep-analyze --provider anthropic` 批量处理所有 relevance >= 0.6 的论文
4. 已分析过的 artifact 重跑时被跳过（幂等）
5. 全量测试 `conda run -n research-radar python -m pytest -v` 通过（现有 111 tests 不受影响）

---

## 7. 不做的事

- **不修改 `run` 命令**（`--full` 在 P3e 实现）
- **不修改 scoring / reporting**（L2 分析结果在 P3b 聚类时才消费）
- **不做 analysis_version 强制重分析**（首次只需要 `v1`，版本升级机制后续再加）
- **不做 L2 分析结果在报告中展示**（P3e Landscape 报告才展示）
- **不抽共享 JSON 解析工具**（如果 `_strip_code_fences` / `_extract_json_payload` 需要复用，可以直接从 `LLMRelevancePipeline` 或 `EnrichmentPipeline` 复制，不做提前抽象）

---

## 8. 实现参考

- **pipeline 结构**：完全照搬 `src/pipelines/enrichment.py` 的结构（`__init__` → `process` → `_run_tasks` → `_enrich_one` → `_parse_response`），只改核心逻辑
- **JSON 解析容错**：参考 `src/pipelines/llm_relevance.py` 中的 `_extract_json_payload` 方法
- **prompt 模板加载**：复用 enrichment 的 `_load_prompt_template` 模式
- **测试模式**：参考 `tests/pipelines/test_enrichment_pipeline.py` 和 `tests/pipelines/test_llm_relevance.py`
