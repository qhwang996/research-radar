"""Daily markdown report generation."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.reporting.base import BaseReportGenerator
from src.reporting.renderer import format_date, truncate

BLOG_LOOKBACK_DAYS = 3
BLOG_RECOMMENDATION_LIMIT = 5
SUMMARY_MAX_LENGTH = 280


class DailyReportGenerator(BaseReportGenerator):
    """Generate a daily markdown report."""

    def generate(self, target_date: date) -> Path:
        """Generate and write the daily report for one UTC day."""

        day_start, day_end = self._day_range(target_date)
        blog_window_start = day_start - timedelta(days=BLOG_LOOKBACK_DAYS - 1)
        read_artifact_ids = self._load_read_artifact_ids()
        recent_scored_artifacts = self._load_scored_artifacts(blog_window_start, day_end)
        blog_recommendations = [
            artifact
            for artifact in recent_scored_artifacts
            if artifact.source_type == SourceType.BLOGS and artifact.id not in read_artifact_ids
        ][:BLOG_RECOMMENDATION_LIMIT]
        metadata = self._load_daily_metadata(day_start, day_end)

        context = {
            "target_date": target_date,
            "generated_at": self._current_time(),
            "blog_recommendations": blog_recommendations,
            "paper_count": metadata["paper_count"],
            "paper_sources": metadata["paper_sources"],
            "daily_blog_count": metadata["daily_blog_count"],
            "database_total": metadata["database_total"],
        }

        return self._write_report("daily", f"{target_date.isoformat()}.md", self.render(context))

    def render(self, context: dict) -> str:
        """Render the daily report into markdown."""

        target_date = context["target_date"]
        generated_at = context["generated_at"]
        blog_recommendations: list[Artifact] = context["blog_recommendations"]
        paper_count: int = context["paper_count"]
        paper_sources: list[str] = context["paper_sources"]
        daily_blog_count: int = context["daily_blog_count"]
        database_total: int = context["database_total"]

        lines = [
            "# Research Radar - 日报",
            f"**日期**: {target_date.isoformat()}",
            f"**生成时间**: {generated_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
            f"## 今日博客推荐（{len(blog_recommendations)} 篇）",
        ]

        if blog_recommendations:
            for rank, artifact in enumerate(blog_recommendations, start=1):
                lines.extend(
                    [
                        "",
                        f"### {rank}. {artifact.title}",
                        f"- **来源**: {artifact.source_name or 'Unknown'}",
                        f"- **发布**: {format_date(artifact.published_at, artifact.year)}",
                        f"- **相关度**: {(artifact.relevance_score or 0.0):.2f}",
                        f"- **URL**: {artifact.source_url}",
                        f"- **摘要**: {self._render_summary(artifact)}",
                    ]
                )
        else:
            lines.extend(["", "暂无符合条件的博客推荐。"])

        lines.extend(
            [
                "",
                "---",
                "",
                "## 漏洞速报",
                "",
                "暂无漏洞数据源",
                "",
                "---",
                "",
                "## 论文动态",
                "",
                self._render_paper_activity(paper_count, paper_sources),
                "",
                "---",
                "",
                "## 统计",
                f"- 今日新增博客数: {daily_blog_count}",
                f"- 数据库总量: {database_total}",
            ]
        )
        return "\n".join(lines)

    def _load_daily_metadata(self, start: datetime, end: datetime) -> dict[str, object]:
        """Load non-recommendation daily counters and paper source names."""

        session = self.session_factory()
        try:
            base_filters = (
                Artifact.created_at >= start,
                Artifact.created_at < end,
                Artifact.status == ArtifactStatus.ACTIVE,
            )
            paper_count = int(
                session.scalar(
                    select(func.count(Artifact.id)).where(
                        *base_filters,
                        Artifact.source_type == SourceType.PAPERS,
                    )
                )
                or 0
            )
            daily_blog_count = int(
                session.scalar(
                    select(func.count(Artifact.id)).where(
                        *base_filters,
                        Artifact.source_type == SourceType.BLOGS,
                    )
                )
                or 0
            )
            database_total = int(
                session.scalar(
                    select(func.count(Artifact.id)).where(Artifact.status == ArtifactStatus.ACTIVE)
                )
                or 0
            )
            source_statement = (
                select(Artifact.source_name)
                .where(
                    *base_filters,
                    Artifact.source_type == SourceType.PAPERS,
                )
                .distinct()
                .order_by(Artifact.source_name.asc())
            )
            paper_sources = [source_name for source_name in session.scalars(source_statement) if source_name]
            return {
                "paper_count": paper_count,
                "paper_sources": paper_sources,
                "daily_blog_count": daily_blog_count,
                "database_total": database_total,
            }
        finally:
            session.close()

    def _render_paper_activity(self, paper_count: int, paper_sources: list[str]) -> str:
        """Render the paper activity callout block."""

        if paper_count <= 0:
            return "> 今日无论文更新。"
        visible_sources = paper_sources[:3]
        source_text = "、".join(visible_sources) if visible_sources else "未知来源"
        if len(paper_sources) > len(visible_sources):
            source_text = f"{source_text} 等"
        return f"> 今日新增 {paper_count} 篇论文（来源：{source_text}）。详见周报。"

    def _render_summary(self, artifact: Artifact) -> str:
        """Return the preferred summary text for a blog recommendation."""

        summary = artifact.abstract or artifact.summary_l1
        if not summary:
            return "暂无摘要。"
        return truncate(summary.strip(), SUMMARY_MAX_LENGTH)
