"""Weekly markdown report generation."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select

from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType
from src.reporting.base import BaseReportGenerator
from src.reporting.renderer import format_score, truncate

PAPER_RECOMMENDATION_LIMIT = 10
PAPER_RELEVANCE_THRESHOLD = 0.6
SUMMARY_MAX_LENGTH = 320


class WeeklyReportGenerator(BaseReportGenerator):
    """Generate a weekly markdown report."""

    def generate(self, target_date: date) -> Path:
        """Generate and write the weekly report for the ISO week."""

        start, end = self._week_range(target_date)
        read_artifact_ids = self._load_read_artifact_ids()
        weekly_artifacts = self._load_scored_artifacts(start, end)
        weekly_blogs = sorted(
            [artifact for artifact in weekly_artifacts if artifact.source_type == SourceType.BLOGS],
            key=lambda artifact: (
                artifact.relevance_score or 0.0,
                artifact.final_score or 0.0,
                artifact.id or 0,
            ),
            reverse=True,
        )
        paper_recommendations = self._load_paper_recommendations(read_artifact_ids)
        weekly_stats = self._load_weekly_stats(start, end)
        iso_year, iso_week, _ = target_date.isocalendar()
        context = {
            "week_id": f"{iso_year}-W{iso_week:02d}",
            "period_start": start.date(),
            "period_end": (end - timedelta(days=1)).date(),
            "generated_at": self._current_time(),
            "paper_recommendations": paper_recommendations,
            "weekly_blogs": weekly_blogs,
            "read_artifact_ids": read_artifact_ids,
            "score_distribution": self._build_score_distribution(weekly_artifacts),
            "relevance_distribution": self._build_relevance_distribution(weekly_artifacts),
            "stats": weekly_stats,
        }
        return self._write_report("weekly", f"{iso_year}-W{iso_week:02d}.md", self.render(context))

    def render(self, context: dict) -> str:
        """Render the weekly report into markdown."""

        week_id = context["week_id"]
        period_start = context["period_start"]
        period_end = context["period_end"]
        generated_at = context["generated_at"]
        paper_recommendations: list[Artifact] = context["paper_recommendations"]
        weekly_blogs: list[Artifact] = context["weekly_blogs"]
        read_artifact_ids: set[int] = context["read_artifact_ids"]
        score_distribution: dict[str, int] = context["score_distribution"]
        relevance_distribution: dict[str, int] = context["relevance_distribution"]
        stats: dict[str, int] = context["stats"]

        lines = [
            "# Research Radar - 周报",
            f"**周**: {week_id}",
            f"**周期**: {period_start.isoformat()} 至 {period_end.isoformat()}",
            f"**生成时间**: {generated_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
            f"## 本周论文推荐阅读（{len(paper_recommendations)} 篇）",
        ]

        if paper_recommendations:
            for rank, artifact in enumerate(paper_recommendations, start=1):
                lines.extend(
                    [
                        "",
                        f"### {rank}. {artifact.title}",
                        f"- **来源**: {artifact.source_name or 'Unknown'}",
                        (
                            "- **评分**: "
                            f"{format_score(artifact.final_score or 0.0, artifact.recency_score, artifact.authority_score, artifact.relevance_score)}"
                        ),
                        f"- **URL**: {artifact.source_url}",
                        f"- **摘要**: {self._render_summary(artifact)}",
                    ]
                )
        else:
            lines.extend(["", "暂无符合条件的未读论文推荐。"])

        lines.extend(
            [
                "",
                "---",
                "",
                "## 本周博客回顾",
                "",
                f"本周共收录 {len(weekly_blogs)} 篇博客文章。",
            ]
        )
        if weekly_blogs:
            lines.extend(
                [
                    "",
                    "| # | 标题 | 来源 | 相关度 | 状态 |",
                    "|---|---|---|---|---|",
                ]
            )
            for rank, artifact in enumerate(weekly_blogs, start=1):
                title = artifact.title.replace("|", "\\|")
                source_name = (artifact.source_name or "Unknown").replace("|", "\\|")
                status_label = "已读" if artifact.id in read_artifact_ids else "未读"
                lines.append(
                    f"| {rank} | {title} | {source_name} | {(artifact.relevance_score or 0.0):.2f} | {status_label} |"
                )
        else:
            lines.extend(["", "本周无新增博客。"])

        lines.extend(
            [
                "",
                "---",
                "",
                "## Relevance Distribution",
                f"- 高相关 (>= 0.6): {relevance_distribution['high']} items",
                f"- 中等 (0.3 - 0.6): {relevance_distribution['medium']} items",
                f"- 低相关 (< 0.3): {relevance_distribution['low']} items",
                "",
                "---",
                "",
                "## Score Distribution",
                f"- >= 0.9: {score_distribution['gte_0_9']} items",
                f"- 0.8-0.9: {score_distribution['between_0_8_0_9']} items",
                f"- 0.7-0.8: {score_distribution['between_0_7_0_8']} items",
                f"- 0.6-0.7: {score_distribution['between_0_6_0_7']} items",
                f"- < 0.6: {score_distribution['lt_0_6']} items",
                "",
                "---",
                "",
                "## 统计",
                f"- 本周新增论文: {stats['weekly_paper_count']} 篇",
                f"- 本周新增博客: {stats['weekly_blog_count']} 篇",
                f"- 数据库总量: {stats['database_total']} 条",
            ]
        )

        return "\n".join(lines)

    def _load_paper_recommendations(self, read_artifact_ids: set[int]) -> list[Artifact]:
        """Load top unread high-relevance papers across the full active corpus."""

        session = self.session_factory()
        try:
            statement = select(Artifact).where(
                Artifact.status == ArtifactStatus.ACTIVE,
                Artifact.source_type == SourceType.PAPERS,
                Artifact.final_score.is_not(None),
                Artifact.relevance_score >= PAPER_RELEVANCE_THRESHOLD,
            )
            if read_artifact_ids:
                statement = statement.where(~Artifact.id.in_(sorted(read_artifact_ids)))
            statement = statement.order_by(
                Artifact.final_score.desc(),
                Artifact.created_at.desc(),
                Artifact.id.desc(),
            ).limit(PAPER_RECOMMENDATION_LIMIT)
            return list(session.scalars(statement))
        finally:
            session.close()

    def _load_weekly_stats(self, start, end) -> dict[str, int]:
        """Load weekly counters shown in the summary section."""

        session = self.session_factory()
        try:
            base_filters = (
                Artifact.created_at >= start,
                Artifact.created_at < end,
                Artifact.status == ArtifactStatus.ACTIVE,
            )
            weekly_paper_count = int(
                session.scalar(
                    select(func.count(Artifact.id)).where(
                        *base_filters,
                        Artifact.source_type == SourceType.PAPERS,
                    )
                )
                or 0
            )
            weekly_blog_count = int(
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
            return {
                "weekly_paper_count": weekly_paper_count,
                "weekly_blog_count": weekly_blog_count,
                "database_total": database_total,
            }
        finally:
            session.close()

    def _render_summary(self, artifact: Artifact) -> str:
        """Return the preferred summary text for a paper recommendation."""

        summary = artifact.abstract or artifact.summary_l1
        if not summary:
            return "暂无摘要。"
        return truncate(summary.strip(), SUMMARY_MAX_LENGTH)

    def _build_score_distribution(self, artifacts: list[Artifact]) -> dict[str, int]:
        """Compute summary and bucketed score distribution."""

        distribution = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "gte_0_9": 0,
            "between_0_8_0_9": 0,
            "between_0_7_0_8": 0,
            "between_0_6_0_7": 0,
            "lt_0_6": 0,
        }
        for artifact in artifacts:
            score = artifact.final_score or 0.0
            if score >= 0.8:
                distribution["high"] += 1
            elif score >= 0.6:
                distribution["medium"] += 1
            else:
                distribution["low"] += 1

            if score >= 0.9:
                distribution["gte_0_9"] += 1
            elif score >= 0.8:
                distribution["between_0_8_0_9"] += 1
            elif score >= 0.7:
                distribution["between_0_7_0_8"] += 1
            elif score >= 0.6:
                distribution["between_0_6_0_7"] += 1
            else:
                distribution["lt_0_6"] += 1
        return distribution

    def _build_relevance_distribution(self, artifacts: list[Artifact]) -> dict[str, int]:
        """Compute a simple relevance-score distribution."""

        distribution = {
            "high": 0,
            "medium": 0,
            "low": 0,
        }
        for artifact in artifacts:
            relevance = artifact.relevance_score or 0.0
            if relevance >= 0.6:
                distribution["high"] += 1
            elif relevance >= 0.3:
                distribution["medium"] += 1
            else:
                distribution["low"] += 1
        return distribution
