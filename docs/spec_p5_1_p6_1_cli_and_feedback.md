# P5.1 + P6.1 CLI & Feedback Collector - Implementation Spec

## 1. Goal

实现完整的 CLI 入口 + Feedback 收集，让系统可以通过命令行运行完整流程。

P5.1 (Feedback Collector) 和 P6.1 (CLI) 合并为一个任务交付。

---

## 2. Dependencies

新增依赖：`click>=8.1.0`（轻量 CLI 框架，无额外重依赖）

添加到 `requirements.txt`。

---

## 3. Directory Structure

```
src/cli/
    __init__.py
    main.py            # click group 入口
    crawl.py           # crawl 子命令
    process.py         # normalize / enrich / score 子命令
    report.py          # report 子命令
    feedback.py        # feedback 子命令

tests/cli/
    __init__.py
    test_feedback.py
    test_commands.py
```

入口点：`python -m src.cli.main` 或 `python -m src.cli`

---

## 4. CLI Commands

### 4.1 Top-level Group

```
research-radar [OPTIONS] COMMAND

Commands:
  crawl       Run crawlers to fetch raw data
  normalize   Process raw JSON into artifacts
  enrich      Generate LLM summaries and tags
  score       Score all artifacts
  report      Generate daily or weekly reports
  feedback    Provide feedback on artifacts
  run         Run full pipeline (normalize → enrich → score → report)
```

### 4.2 `crawl`

```
research-radar crawl [OPTIONS]

Options:
  --source TEXT     Specific source to crawl (e.g. ndss, sp, portswigger).
                    If omitted, crawl all registered sources.
  --years TEXT      Comma-separated years (e.g. "2025,2026"). Default: current year.
  --output-dir PATH Output directory for raw JSON. Default: data/raw
```

Implementation:
- Use the existing crawler registry to get crawlers
- Call `crawler.fetch_papers(years)` + `crawler.save_raw(papers, output_dir)`
- Log results (source, count, path)

### 4.3 `normalize`

```
research-radar normalize [OPTIONS]

Options:
  --input-dir PATH   Directory of raw JSON files. Default: data/raw
  --recursive        Scan subdirectories recursively. Default: true
```

Implementation:
- Instantiate `NormalizationPipeline`
- Call `pipeline.process(input_dir)`

### 4.4 `enrich`

```
research-radar enrich [OPTIONS]

Options:
  --provider TEXT    LLM provider: "openai" or "anthropic". Default: "openai"
  --artifact-id INT Target a specific artifact by DB id. Omit for all unenriched.
```

Implementation:
- Instantiate `LLMClient(provider=provider)`
- Instantiate `EnrichmentPipeline(llm_client=client)`
- Call `pipeline.process(artifact_id or None)`

### 4.5 `score`

```
research-radar score [OPTIONS]
```

No options needed. Scores all active artifacts that have no `final_score` or forces rescore.

Implementation:
- Instantiate `ScoringEngine`
- Call `engine.score_all()`

### 4.6 `report`

```
research-radar report [OPTIONS]

Options:
  --type TEXT     Report type: "daily" or "weekly". Required.
  --date TEXT     Target date in YYYY-MM-DD format. Default: today.
```

Implementation:
- Parse date string
- Instantiate `DailyReportGenerator` or `WeeklyReportGenerator`
- Call `generator.generate(target_date)`
- Print the output path

### 4.7 `feedback`

```
research-radar feedback [OPTIONS]

Options:
  --artifact-id INT     Target artifact DB id. Required.
  --type TEXT           Feedback type: "like", "dislike", or "note". Required.
  --note TEXT           Note text (required when --type=note, optional for like/dislike).
```

Implementation:
- Validate artifact exists in DB
- Create `FeedbackEvent` with:
  - `target_type = FeedbackTargetType.ARTIFACT`
  - `target_id = str(artifact_id)`
  - `feedback_type` mapped from --type
  - `content = {"note": note}` if note provided, else `{}`
- Save via `FeedbackRepository`
- Print confirmation

### 4.8 `run` (convenience)

```
research-radar run [OPTIONS]

Options:
  --skip-crawl       Skip the crawl step.
  --provider TEXT     LLM provider for enrichment. Default: "openai"
  --report-type TEXT  Report type to generate. Default: "daily"
  --date TEXT         Target date. Default: today.
```

Implementation: sequentially call normalize → enrich → score → report.
Crawl is optional because raw data may already exist.

---

## 5. Feedback Design (P5.1)

### 5.1 Phase 1 Scope

- Target: **artifact only** (theme/direction deferred to Phase 2)
- Actions: **like / dislike / note**
- Storage: `FeedbackEvent` in database (append-only)
- **Does NOT affect scoring** in Phase 1 (feedback_multiplier deferred to Phase 2)

### 5.2 FeedbackEvent Content Schema

```python
# like
{"type": "like"}
{"type": "like", "note": "Interesting approach to XSS detection"}

# dislike
{"type": "dislike"}
{"type": "dislike", "note": "Too theoretical, no practical impact"}

# note
{"type": "note", "note": "Compare with the USENIX 2025 paper on similar topic"}
```

### 5.3 Deferred to Phase 2

- [ ] Theme-level feedback (confirm/reject themes)
- [ ] Direction-level feedback (pros/cons/unknowns)
- [ ] Feedback multiplier integration into scoring (doc07 Section 5)
- [ ] ProfileUpdater (auto-learn preferences from feedback patterns)
- [ ] Interactive feedback mode (show artifact → prompt for feedback)

---

## 6. CLI `__main__` Entry

```python
# src/cli/__main__.py
from src.cli.main import cli

cli()
```

This enables `python -m src.cli` invocation.

---

## 7. Error Handling

- All commands catch top-level exceptions and print a user-friendly error message + exit code 1
- `click.ClickException` for user input errors (missing required options, invalid date format)
- Pipeline/LLM/DB errors logged with traceback at DEBUG level, summary at ERROR level
- `--verbose` flag on the top-level group to enable DEBUG logging

---

## 8. Testing

### 8.1 Feedback Tests (`test_feedback.py`)

- `test_feedback_like_creates_event`: like on valid artifact creates FeedbackEvent
- `test_feedback_dislike_creates_event`: dislike on valid artifact
- `test_feedback_note_requires_text`: note without --note raises error
- `test_feedback_invalid_artifact_id`: non-existent artifact id raises error
- `test_feedback_events_are_append_only`: multiple feedbacks on same artifact all persist

### 8.2 Command Tests (`test_commands.py`)

Use `click.testing.CliRunner` for isolated CLI invocation.

- `test_report_command_generates_file`: report --type daily produces a file
- `test_run_command_executes_pipeline`: run with --skip-crawl completes without error
- `test_feedback_command_end_to_end`: feedback --artifact-id X --type like creates event in DB

### 8.3 Test Strategy

- Use in-memory SQLite
- Mock LLM client for enrich tests
- Use `CliRunner` (no subprocess needed)
- Use `tmp_path` for file output

---

## 9. NOT in Scope

- Scheduling / cron (P6.2, deferred)
- Interactive CLI / TUI
- Theme / Direction feedback
- Feedback → scoring integration
- `crawl` command live network tests (existing crawler tests cover parsing)
