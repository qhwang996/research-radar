"""Landscape (weekly) markdown report generation with gap analysis."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.artifact import Artifact
from src.models.candidate_direction import CandidateDirection
from src.models.enums import ArtifactStatus, DirectionStatus, SourceType, ThemeStatus
from src.models.research_gap import ResearchGap
from src.models.theme import Theme
from src.reporting.base import BaseReportGenerator
from src.reporting.renderer import format_date, truncate
from src.repositories.candidate_direction_repository import CandidateDirectionRepository
from src.repositories.research_gap_repository import ResearchGapRepository
from src.repositories.theme_repository import ThemeRepository

RECOMMENDED_READING_LIMIT = 10
BLOG_REVIEW_LIMIT = 10


def _star_rating(score: float | None) -> str:
    """Convert a 0.0-1.0 score to a star rating string."""

    if score is None:
        return "N/A"
    stars = round(score * 5)
    return "★" * stars + "☆" * (5 - stars)


class LandscapeReportGenerator(BaseReportGenerator):
    """Generate a weekly landscape report with themes, gaps, and directions."""

    def generate(self, target_date: date) -> Path:
        """Generate the landscape report for the ISO week containing target_date."""

        week_start, week_end = self._week_range(target_date)
        iso_year, iso_week, _ = target_date.isocalendar()
        week_id = f"{iso_year}-W{iso_week:02d}"

        session = self.session_factory()
        try:
            themes = ThemeRepository(session).list_active_or_core()
            gaps = ResearchGapRepository(session).list_active()
            directions = CandidateDirectionRepository(session).list_active()

            # Load top papers for recommended reading
            read_ids = self._load_read_artifact_ids()
            stmt = (
                select(Artifact)
                .where(Artifact.status == ArtifactStatus.ACTIVE)
                .where(Artifact.source_type == SourceType.PAPERS)
                .where(Artifact.final_score.is_not(None))
                .order_by(Artifact.final_score.desc())
                .limit(50)
            )
            top_papers = [
                a for a in session.scalars(stmt)
                if a.id not in read_ids
            ][:RECOMMENDED_READING_LIMIT]

            # Load recent blogs
            blog_stmt = (
                select(Artifact)
                .where(Artifact.status == ArtifactStatus.ACTIVE)
                .where(Artifact.source_type == SourceType.BLOGS)
                .where(Artifact.final_score.is_not(None))
                .order_by(Artifact.created_at.desc())
                .limit(BLOG_REVIEW_LIMIT)
            )
            recent_blogs = list(session.scalars(blog_stmt))

            # Stats
            total_count = session.scalar(
                select(func.count(Artifact.id)).where(Artifact.status == ArtifactStatus.ACTIVE)
            ) or 0
            paper_count = session.scalar(
                select(func.count(Artifact.id))
                .where(Artifact.status == ArtifactStatus.ACTIVE)
                .where(Artifact.source_type == SourceType.PAPERS)
            ) or 0
            analyzed_count = session.scalar(
                select(func.count(Artifact.id))
                .where(Artifact.status == ArtifactStatus.ACTIVE)
                .where(Artifact.summary_l2.is_not(None))
                .where(Artifact.summary_l2 != "")
            ) or 0
        finally:
            session.close()

        context = {
            "week_id": week_id,
            "week_start": week_start.date(),
            "week_end": (week_end.date()),
            "generated_at": self._current_time(),
            "themes": themes,
            "gaps": gaps,
            "directions": directions,
            "top_papers": top_papers,
            "recent_blogs": recent_blogs,
            "total_count": total_count,
            "paper_count": paper_count,
            "analyzed_count": analyzed_count,
            "theme_count": len(themes),
            "direction_count": len(directions),
            "gap_count": len(gaps),
        }

        return self._write_report("weekly", f"{week_id}.md", self.render(context))

    def render(self, context: dict) -> str:
        """Render the landscape report into markdown."""

        lines: list[str] = []
        lines.append(f"# Research Radar - 研究前沿全景报告")
        lines.append(f"**周**: {context['week_id']}")
        lines.append(f"**周期**: {context['week_start']} 至 {context['week_end']}")
        lines.append(f"**生成时间**: {format_date(context['generated_at'])}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Section 1: Theme map
        themes = context["themes"]
        lines.append("## 研究前沿地图")
        lines.append("")
        if themes:
            lines.append(f"当前追踪 {len(themes)} 个研究子领域。")
            lines.append("")
            for i, theme in enumerate(themes, 1):
                trend_icon = {"growing": "▲", "declining": "▼", "stable": "—"}.get(
                    theme.trend_direction or "", "?"
                )
                lines.append(f"### {i}. {theme.name} {trend_icon}")
                if theme.description:
                    lines.append(f"- **描述**: {theme.description}")
                lines.append(f"- **论文数**: {theme.artifact_count}")
                if theme.methodology_tags:
                    lines.append(f"- **代表方法**: {', '.join(theme.methodology_tags[:5])}")
                if theme.open_questions:
                    lines.append(f"- **关键开放问题**:")
                    for q in theme.open_questions[:3]:
                        lines.append(f"  - {q}")
                lines.append("")
        else:
            lines.append("暂无研究子领域数据。请先运行 `cluster` 命令。")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Section 2: Gap analysis
        gaps = context["gaps"]
        lines.append("## 学术-工业空白分析")
        lines.append("")
        if gaps:
            lines.append(f"检测到 {len(gaps)} 个研究空白（工业界关注但学术界尚未充分解决）：")
            lines.append("")
            for i, gap in enumerate(gaps[:5], 1):
                lines.append(f"### 空白 {i}: {gap.topic}  (gap_score: {gap.gap_score:.2f})")
                lines.append(f"- **工业需求**: {gap.demand_frequency} 个独立来源提到")
                for sig in (gap.demand_signals or [])[:3]:
                    lines.append(f"  - [{sig.get('source_name', 'Unknown')}] {truncate(sig.get('problem_described', ''), 100)}")
                lines.append(f"- **学术覆盖**: {gap.academic_coverage:.0%}")
                if gap.description:
                    lines.append(f"- **空白性质**: {gap.description}")
                lines.append("")
        else:
            lines.append("暂无空白数据。请先运行 `extract-signals` 和 `detect-gaps` 命令。")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Section 3: Candidate directions
        directions = context["directions"]
        lines.append("## 候选研究方向")
        lines.append("")
        if directions:
            for i, d in enumerate(directions, 1):
                lines.append(f"### 方向 {i}: {d.title}")
                if d.description:
                    lines.append(f"- **概述**: {d.description}")
                if d.rationale:
                    lines.append(f"- **为什么有价值**: {d.rationale}")
                if d.why_now:
                    lines.append(f"- **为什么现在**: {d.why_now}")
                lines.append(
                    f"- **新颖性**: {_star_rating(d.novelty_score)}  |  "
                    f"**影响力**: {_star_rating(d.impact_score)}  |  "
                    f"**可行性**: {_star_rating(d.feasibility_score)}  |  "
                    f"**门槛**: {_star_rating(d.barrier_score)}"
                )
                if d.open_questions:
                    lines.append("- **待解决问题**:")
                    for q in d.open_questions[:3]:
                        lines.append(f"  - {q}")
                lines.append("")
        else:
            lines.append("暂无候选方向。请先运行 `synthesize` 命令。")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Section 4: Recommended reading
        top_papers = context["top_papers"]
        lines.append("## 推荐阅读")
        lines.append("")
        if top_papers:
            lines.append("| # | 标题 | 来源 | 相关度 | 状态 |")
            lines.append("|---|------|------|--------|------|")
            for i, p in enumerate(top_papers, 1):
                rel = f"{p.relevance_score:.2f}" if p.relevance_score else "N/A"
                lines.append(f"| {i} | {truncate(p.title, 60)} | {p.source_name or 'Unknown'} | {rel} | 未读 |")
            lines.append("")
        else:
            lines.append("暂无推荐论文。")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Section 5: Blog review
        recent_blogs = context["recent_blogs"]
        lines.append("## 博客回顾")
        lines.append("")
        if recent_blogs:
            lines.append("| # | 标题 | 来源 | 相关度 |")
            lines.append("|---|------|------|--------|")
            for i, b in enumerate(recent_blogs, 1):
                rel = f"{b.relevance_score:.2f}" if b.relevance_score else "N/A"
                lines.append(f"| {i} | {truncate(b.title, 60)} | {b.source_name or 'Unknown'} | {rel} |")
            lines.append("")
        else:
            lines.append("暂无博客数据。")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Section 6: Stats
        lines.append("## 统计")
        lines.append(f"- 数据库总量: {context['total_count']}")
        lines.append(f"- 论文总数: {context['paper_count']}（已深度分析: {context['analyzed_count']}）")
        lines.append(f"- 研究子领域数: {context['theme_count']}")
        lines.append(f"- 研究空白数: {context['gap_count']}")
        lines.append(f"- 累计候选方向数: {context['direction_count']}")
        lines.append("")

        return "\n".join(lines)
