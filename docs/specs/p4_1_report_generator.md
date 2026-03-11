# P4.1 Report Generator - Implementation Spec

## 1. Goal

实现 Daily + Weekly 两种 Markdown 报告生成器，完成 crawl -> normalize -> score -> **report** 闭环。

Phase 1 不依赖 LLM，所有内容直接从数据库字段获取。

---

## 2. Directory Structure

```
src/reporting/
    __init__.py
    base.py            # BaseReportGenerator
    daily.py           # DailyReportGenerator
    weekly.py          # WeeklyReportGenerator
    renderer.py        # Markdown rendering helpers

tests/test_reporting/
    __init__.py
    test_daily.py
    test_weekly.py
```

输出目录：
```
data/reports/
    daily/    # YYYY-MM-DD.md
    weekly/   # YYYY-WXX.md
```

---

## 3. Interface

### 3.1 BaseReportGenerator

```python
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from sqlalchemy.orm import Session, sessionmaker

class BaseReportGenerator(ABC):
    """Base class for report generators."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        output_dir: Path | None = None,
    ) -> None: ...

    @abstractmethod
    def generate(self, target_date: date) -> Path:
        """
        Generate a report for the given date and write it to disk.

        Args:
            target_date: The reference date for the report.
                - DailyReport: artifacts fetched/published on target_date
                - WeeklyReport: the ISO week containing target_date

        Returns:
            Path to the written markdown file.
        """

    @abstractmethod
    def render(self, context: dict) -> str:
        """Render the report context into a markdown string."""
```

### 3.2 DailyReportGenerator

```python
class DailyReportGenerator(BaseReportGenerator):
    """Generate a daily markdown report."""

    def generate(self, target_date: date) -> Path:
        """
        Steps:
        1. Query artifacts where created_at falls on target_date,
           status = ACTIVE, final_score is not None
        2. Filter: only include score >= 0.6
        3. Group by source_type
        4. Sort within each group by final_score desc
        5. Build context dict
        6. Render markdown
        7. Write to data/reports/daily/YYYY-MM-DD.md
        """
```

**Output file**: `data/reports/daily/{target_date}.md`

**Report structure** (see doc08 Section 2.2, adapted for Phase 1):

```markdown
# Research Radar - Daily Report
**Date**: YYYY-MM-DD
**Generated**: YYYY-MM-DD HH:MM

---

## Summary
- Total artifacts: X
- High-value (score >= 0.8): Y
- Sources: Papers N, Blogs M

---

## High Value (score >= 0.8)

### 1. [Artifact Title]
- **Source**: source_name (source_type)
- **Published**: YYYY or YYYY-MM-DD
- **Score**: 0.95 (recency: 0.90, authority: 1.00)
- **URL**: source_url
- **Abstract**: first 200 chars of abstract if available...

### 2. ...

---

## Medium Value (0.6 <= score < 0.8)

### 1. [Artifact Title]
- **Source**: source_name (source_type)
- **Published**: YYYY or YYYY-MM-DD
- **Score**: 0.72 (recency: 0.64, authority: 0.80)
- **URL**: source_url

---

## Statistics
- Papers: X (top-tier: A)
- Blogs: B
```

**Display rules**:
- score >= 0.8: show abstract (truncated to 200 chars)
- 0.6 <= score < 0.8: no abstract, metadata only
- score < 0.6: excluded from report

### 3.3 WeeklyReportGenerator

```python
class WeeklyReportGenerator(BaseReportGenerator):
    """Generate a weekly markdown report."""

    def generate(self, target_date: date) -> Path:
        """
        Steps:
        1. Compute ISO week range (Monday-Sunday) from target_date
        2. Query artifacts where created_at falls within the week,
           status = ACTIVE, final_score is not None
        3. Build statistics
        4. Select Top 10 by final_score
        5. Compute score distribution
        6. Build context dict
        7. Render markdown
        8. Write to data/reports/weekly/YYYY-WXX.md
        """
```

**Output file**: `data/reports/weekly/{year}-W{week:02d}.md`

**Report structure** (see doc08 Section 3.2, simplified for Phase 1):

```markdown
# Research Radar - Weekly Report
**Week**: YYYY-WXX
**Period**: YYYY-MM-DD to YYYY-MM-DD
**Generated**: YYYY-MM-DD HH:MM

---

## Summary
Total artifacts this week: X
- High (>= 0.8): A
- Medium (0.6-0.8): B
- Low (< 0.6): C

---

## Content Breakdown
- Papers: X (top-tier: Y)
- Blogs: Z

---

## Top 10 Artifacts

### 1. [Artifact Title]
- **Type**: Papers / Blogs
- **Source**: source_name
- **Score**: 0.98 (recency: 0.95, authority: 1.00)
- **Published**: YYYY-MM-DD
- **URL**: source_url
- **Abstract**: abstract text (truncated to 300 chars)...

### 2. ...

(up to 10 items)

---

## Score Distribution
- >= 0.9: X items
- 0.8-0.9: Y items
- 0.7-0.8: Z items
- 0.6-0.7: W items
- < 0.6: V items

---

## All Artifacts by Source

### Papers (X items)
1. [Title] - score: 0.95
2. [Title] - score: 0.90
...

### Blogs (Y items)
1. [Title] - score: 0.75
2. [Title] - score: 0.70
...
```

**Phase 1 omissions** (compared to doc08):
- No "Candidate Research Directions" section (needs LLM, deferred to P2.3+)
- No "Theme Evolution" section (needs Theme model, deferred)
- No "Action Items" section (needs feedback system, deferred to P5.1)

### 3.4 Renderer Helpers

`renderer.py` provides pure functions for markdown formatting:

```python
def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max_length, appending suffix if truncated."""

def format_score(final: float, recency: float | None, authority: float | None) -> str:
    """Format score with breakdown, e.g. '0.95 (recency: 0.90, authority: 1.00)'."""

def format_date(d: date | datetime | None, year: int | None = None) -> str:
    """Format date for display. Falls back to year if no precise date."""

def format_artifact_entry(
    artifact: Artifact,
    *,
    rank: int | None = None,
    show_abstract: bool = False,
    abstract_max_length: int = 200,
) -> str:
    """Render a single artifact as a markdown block."""
```

---

## 4. Data Access

### 4.1 Query Requirements

The generators query artifacts from the database. Add these methods to `ArtifactRepository`:

```python
class ArtifactRepository(BaseRepository[Artifact]):

    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        status: ArtifactStatus = ArtifactStatus.ACTIVE,
    ) -> list[Artifact]:
        """
        Return artifacts with created_at in [start, end),
        filtered by status, ordered by final_score desc.
        Only include artifacts where final_score is not None.
        """
```

**Note**: Use `created_at` (when the artifact entered the DB) as the range filter, not `published_at`. This ensures we capture all newly processed artifacts regardless of their original publication date.

### 4.2 Date Range Computation

- **Daily**: `start = target_date 00:00:00 UTC`, `end = target_date+1 00:00:00 UTC`
- **Weekly**: `start = Monday 00:00:00 UTC`, `end = next Monday 00:00:00 UTC`
  Use `date.isocalendar()` to determine the ISO week.

---

## 5. File I/O

- Use `pathlib.Path` throughout
- Create output directories automatically (`mkdir(parents=True, exist_ok=True)`)
- Write with UTF-8 encoding
- If the file already exists, overwrite it (idempotent regeneration)
- Log the output path after writing

---

## 6. Error Handling

- If no artifacts exist for the date range, still generate a report with "No artifacts found" message
- Database errors should propagate (don't swallow)
- File write errors should propagate
- Log warnings for artifacts missing scores

---

## 7. Testing

### 7.1 Fixtures

Create a helper to build test artifacts with controlled scores and dates:

```python
def make_artifact(
    title: str = "Test Paper",
    source_type: SourceType = SourceType.PAPERS,
    source_name: str = "S&P",
    source_tier: str = "top-tier",
    final_score: float = 0.9,
    recency_score: float = 0.8,
    authority_score: float = 1.0,
    year: int = 2026,
    created_at: datetime | None = None,
    **kwargs,
) -> Artifact: ...
```

### 7.2 Test Cases

**DailyReportGenerator**:
- `test_daily_empty`: no artifacts -> report with "No artifacts found"
- `test_daily_score_filter`: artifacts with score < 0.6 excluded from report content
- `test_daily_high_value_has_abstract`: score >= 0.8 entries show abstract
- `test_daily_medium_value_no_abstract`: 0.6 <= score < 0.8 entries omit abstract
- `test_daily_sorted_by_score`: artifacts appear in descending score order
- `test_daily_file_written`: output file exists at correct path
- `test_daily_idempotent`: running twice produces same file

**WeeklyReportGenerator**:
- `test_weekly_empty`: no artifacts -> report with "No artifacts found"
- `test_weekly_top_10`: only top 10 shown in top section
- `test_weekly_score_distribution`: distribution counts are correct
- `test_weekly_content_breakdown`: source type counts are correct
- `test_weekly_date_range`: only artifacts within the ISO week are included
- `test_weekly_file_naming`: output file named YYYY-WXX.md correctly

**Renderer**:
- `test_truncate_short_text`: no truncation when text fits
- `test_truncate_long_text`: truncated with suffix
- `test_format_score`: correct string format
- `test_format_date_with_datetime`: full date format
- `test_format_date_with_year_only`: falls back to year

### 7.3 Test Strategy

- All tests use in-memory SQLite (same pattern as existing tests)
- No file I/O in unit tests for renderer — test string output directly
- For generator tests, use `tmp_path` fixture for output directory

---

## 8. Dependencies

No new dependencies. Uses only:
- `sqlalchemy` (already installed)
- `pathlib`, `datetime` (stdlib)

---

## 9. NOT in Scope

- LLM-generated summaries or directions
- Theme grouping
- Feedback-based action items
- Monthly reports
- Scheduling (cron/timer)
- HTML/PDF output
