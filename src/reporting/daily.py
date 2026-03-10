"""Daily markdown report generation."""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path

from src.models.artifact import Artifact
from src.reporting.base import BaseReportGenerator
from src.reporting.renderer import format_artifact_entry


class DailyReportGenerator(BaseReportGenerator):
    """Generate a daily markdown report."""

    def generate(self, target_date: date) -> Path:
        """Generate and write the daily report for one UTC day."""

        start, end = self._day_range(target_date)
        artifacts = self._load_scored_artifacts(start, end)
        included = [artifact for artifact in artifacts if (artifact.final_score or 0.0) >= 0.6]
        high_value = [artifact for artifact in included if (artifact.final_score or 0.0) >= 0.8]
        medium_value = [artifact for artifact in included if 0.6 <= (artifact.final_score or 0.0) < 0.8]

        context = {
            "target_date": target_date,
            "generated_at": self._current_time(),
            "included": included,
            "high_value": high_value,
            "medium_value": medium_value,
            "stats": self._build_stats(included),
        }

        return self._write_report("daily", f"{target_date.isoformat()}.md", self.render(context))

    def render(self, context: dict) -> str:
        """Render the daily report into markdown."""

        target_date = context["target_date"]
        generated_at = context["generated_at"]
        included: list[Artifact] = context["included"]
        high_value: list[Artifact] = context["high_value"]
        medium_value: list[Artifact] = context["medium_value"]
        stats: dict[str, int] = context["stats"]

        lines = [
            "# Research Radar - Daily Report",
            f"**Date**: {target_date.isoformat()}",
            f"**Generated**: {generated_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
            "## Summary",
            f"- Total artifacts: {len(included)}",
            f"- High-value (score >= 0.8): {len(high_value)}",
            f"- Sources: Papers {stats['papers']}, Blogs {stats['blogs']}, Advisories {stats['advisories']}",
            "",
        ]

        if not included:
            lines.extend(
                [
                    "No artifacts found for this date.",
                    "",
                    "---",
                    "",
                    "## Statistics",
                    "- Papers: 0 (top-tier: 0)",
                    "- Blogs: 0",
                    "- Advisories: 0",
                ]
            )
            return "\n".join(lines)

        lines.extend(
            [
                "---",
                "",
                "## High Value (score >= 0.8)",
            ]
        )
        if high_value:
            for rank, artifact in enumerate(high_value, start=1):
                lines.extend(
                    [
                        "",
                        format_artifact_entry(
                            artifact,
                            rank=rank,
                            show_abstract=True,
                            abstract_max_length=200,
                        ),
                    ]
                )
        else:
            lines.extend(["", "No high-value artifacts found."])

        lines.extend(
            [
                "",
                "---",
                "",
                "## Medium Value (0.6 <= score < 0.8)",
            ]
        )
        if medium_value:
            for rank, artifact in enumerate(medium_value, start=1):
                lines.extend(
                    [
                        "",
                        format_artifact_entry(
                            artifact,
                            rank=rank,
                            show_abstract=False,
                        ),
                    ]
                )
        else:
            lines.extend(["", "No medium-value artifacts found."])

        lines.extend(
            [
                "",
                "---",
                "",
                "## Statistics",
                f"- Papers: {stats['papers']} (top-tier: {stats['top_tier_papers']})",
                f"- Blogs: {stats['blogs']}",
                f"- Advisories: {stats['advisories']}",
            ]
        )
        return "\n".join(lines)

    def _build_stats(self, artifacts: list[Artifact]) -> dict[str, int]:
        """Compute summary statistics for included daily artifacts."""

        counts = Counter(getattr(artifact.source_type, "value", str(artifact.source_type)) for artifact in artifacts)
        top_tier_papers = sum(
            1
            for artifact in artifacts
            if getattr(artifact.source_type, "value", str(artifact.source_type)) == "papers"
            and artifact.source_tier == "top-tier"
        )
        return {
            "papers": counts.get("papers", 0),
            "blogs": counts.get("blogs", 0),
            "advisories": counts.get("advisories", 0),
            "top_tier_papers": top_tier_papers,
        }
