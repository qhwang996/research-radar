"""Weekly markdown report generation."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from src.models.artifact import Artifact
from src.reporting.base import BaseReportGenerator
from src.reporting.renderer import (
    format_artifact_entry,
    format_date,
    format_source_type_label,
)


class WeeklyReportGenerator(BaseReportGenerator):
    """Generate a weekly markdown report."""

    def generate(self, target_date: date) -> Path:
        """Generate and write the weekly report for the ISO week."""

        start, end = self._week_range(target_date)
        artifacts = self._load_scored_artifacts(start, end)
        iso_year, iso_week, _ = target_date.isocalendar()
        context = {
            "week_id": f"{iso_year}-W{iso_week:02d}",
            "period_start": start.date(),
            "period_end": (end - timedelta(days=1)).date(),
            "generated_at": self._current_time(),
            "artifacts": artifacts,
            "top_artifacts": artifacts[:10],
            "content_breakdown": self._build_source_breakdown(artifacts),
            "score_distribution": self._build_score_distribution(artifacts),
            "grouped_artifacts": self._group_by_source_type(artifacts),
        }
        return self._write_report("weekly", f"{iso_year}-W{iso_week:02d}.md", self.render(context))

    def render(self, context: dict) -> str:
        """Render the weekly report into markdown."""

        week_id = context["week_id"]
        period_start = context["period_start"]
        period_end = context["period_end"]
        generated_at = context["generated_at"]
        artifacts: list[Artifact] = context["artifacts"]
        top_artifacts: list[Artifact] = context["top_artifacts"]
        content_breakdown: dict[str, int] = context["content_breakdown"]
        score_distribution: dict[str, int] = context["score_distribution"]
        grouped_artifacts: dict[str, list[Artifact]] = context["grouped_artifacts"]

        lines = [
            "# Research Radar - Weekly Report",
            f"**Week**: {week_id}",
            f"**Period**: {period_start.isoformat()} to {period_end.isoformat()}",
            f"**Generated**: {generated_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
            "## Summary",
            f"Total artifacts this week: {len(artifacts)}",
            f"- High (>= 0.8): {score_distribution['high']}",
            f"- Medium (0.6-0.8): {score_distribution['medium']}",
            f"- Low (< 0.6): {score_distribution['low']}",
            "",
            "---",
            "",
            "## Content Breakdown",
            f"- Papers: {content_breakdown['papers']} (top-tier: {content_breakdown['top_tier_papers']})",
            f"- Blogs: {content_breakdown['blogs']}",
            f"- Advisories: {content_breakdown['advisories']}",
            "",
        ]

        if not artifacts:
            lines.extend(
                [
                    "No artifacts found for this week.",
                    "",
                    "---",
                    "",
                    "## Score Distribution",
                    "- >= 0.9: 0 items",
                    "- 0.8-0.9: 0 items",
                    "- 0.7-0.8: 0 items",
                    "- 0.6-0.7: 0 items",
                    "- < 0.6: 0 items",
                    "",
                    "---",
                    "",
                    "## All Artifacts by Source",
                    "",
                    "No artifacts found.",
                ]
            )
            return "\n".join(lines)

        lines.extend(
            [
                "---",
                "",
                "## Top 10 Artifacts",
            ]
        )
        for rank, artifact in enumerate(top_artifacts, start=1):
            lines.extend(
                [
                    "",
                    format_artifact_entry(
                        artifact,
                        rank=rank,
                        show_abstract=True,
                        abstract_max_length=300,
                    ),
                ]
            )

        lines.extend(
            [
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
                "## All Artifacts by Source",
            ]
        )

        for source_type, items in grouped_artifacts.items():
            lines.extend(
                [
                    "",
                    f"### {format_source_type_label(source_type)} ({len(items)} items)",
                ]
            )
            for index, artifact in enumerate(items, start=1):
                lines.append(
                    f"{index}. [{artifact.title}] - score: {(artifact.final_score or 0.0):.2f} "
                    f"- source: {artifact.source_name or 'Unknown'} "
                    f"- published: {format_date(artifact.published_at, artifact.year)}"
                )

        return "\n".join(lines)

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

    def _group_by_source_type(self, artifacts: list[Artifact]) -> dict[str, list[Artifact]]:
        """Group artifacts by source type while preserving score ordering."""

        grouped: defaultdict[str, list[Artifact]] = defaultdict(list)
        for artifact in artifacts:
            key = getattr(artifact.source_type, "value", str(artifact.source_type))
            grouped[key].append(artifact)
        return dict(grouped)
