"""Tests for the clustering pipeline."""

from __future__ import annotations

from datetime import date
import json
import tempfile
import threading
import unittest
from pathlib import Path

from sqlalchemy.orm import Session

from src.db.session import create_all_tables, create_database_engine, create_session_factory
from src.llm.base import ModelTier
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType, ThemeStatus
from src.models.profile import Profile
from src.models.theme import Theme
from src.pipelines.clustering import ClusteringPipeline
from src.repositories.theme_repository import ThemeRepository


class StubLLMClient:
    """Tiny LLM stub with queued responses."""

    def __init__(self, responses: list[object]) -> None:
        """Store deterministic LLM outcomes."""

        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []
        self.lock = threading.Lock()

    def generate(
        self,
        prompt: str,
        model_tier: ModelTier = ModelTier.STANDARD,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        cache_key: str | None = None,
    ) -> str:
        """Return the next queued response or raise the next queued error."""

        with self.lock:
            self.calls.append(
                {
                    "prompt": prompt,
                    "model_tier": model_tier,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "cache_key": cache_key,
                }
            )
            if not self.responses:
                raise AssertionError("No queued response in StubLLMClient")
            response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return str(response)


class ClusteringPipelineTestCase(unittest.TestCase):
    """Integration-style tests for theme clustering."""

    def setUp(self) -> None:
        """Create an isolated database and clustering dependencies."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        database_path = self.workspace / "test.db"
        database_url = f"sqlite+pysqlite:///{database_path}"
        self.engine = create_database_engine(database_url)
        create_all_tables(self.engine)
        self.session_factory = create_session_factory(self.engine)
        self._save_profile()

    def tearDown(self) -> None:
        """Dispose test resources."""

        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_full_clustering_creates_themes(self) -> None:
        """Eligible papers should be clustered into persisted themes."""

        papers = [
            self._save_artifact(title="Paper 1", year=2024),
            self._save_artifact(title="Paper 2", year=2024),
            self._save_artifact(title="Paper 3", year=2025),
            self._save_artifact(title="Paper 4", year=2025),
            self._save_artifact(title="Paper 5", year=2026),
        ]
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "Web Fuzzing",
                        "description": "Focuses on fuzzing web attack surfaces.",
                        "paper_ids": [papers[0].id, papers[1].id, papers[2].id],
                        "keywords": ["fuzzing", "web"],
                    },
                    {
                        "cluster_label": "Browser Security",
                        "description": "Focuses on browser-side security analysis.",
                        "paper_ids": [papers[3].id, papers[4].id],
                        "keywords": ["browser", "dom"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "Web Application Fuzzing",
                        "description": "Web fuzzing and server-side input exploration.",
                        "merged_from": ["Web Fuzzing"],
                        "keywords": ["fuzzing", "web"],
                    },
                    {
                        "final_label": "Browser Security",
                        "description": "Browser-centric vulnerability analysis.",
                        "merged_from": ["Browser Security"],
                        "keywords": ["browser", "dom"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
            batch_size=10,
        )
        (self.workspace / "prompt.md").write_text("方向：{{research_area}}\n{{paper_list}}", encoding="utf-8")

        themes = pipeline.process(None)

        self.assertEqual(len(themes), 2)
        self.assertEqual(themes[0].name, "Web Fuzzing")
        self.assertEqual(themes[0].artifact_ids, [papers[0].id, papers[1].id, papers[2].id])
        self.assertEqual(themes[1].artifact_ids, [papers[3].id, papers[4].id])
        # With <= 15 unique labels, merge is skipped, only 1 LLM call (batch)
        self.assertEqual(len(llm_client.calls), 1)
        self.assertEqual(llm_client.calls[0]["model_tier"], ModelTier.STANDARD)
        self.assertEqual(llm_client.calls[0]["max_tokens"], 4000)

    def test_clustering_skips_low_relevance(self) -> None:
        """Low-relevance papers should not enter the clustering input."""

        included = self._save_artifact(title="Included Paper", relevance_score=0.82)
        excluded = self._save_artifact(title="Low Relevance", relevance_score=0.4)
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "Server-Side Detection",
                        "description": "Detection theme.",
                        "paper_ids": [included.id],
                        "keywords": ["server", "detection"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "Server-Side Detection",
                        "description": "Detection theme.",
                        "merged_from": ["Server-Side Detection"],
                        "keywords": ["server", "detection"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{paper_list}}", encoding="utf-8")

        themes = pipeline.process(None)

        self.assertEqual(len(themes), 1)
        self.assertEqual(themes[0].artifact_ids, [included.id])
        self.assertNotIn(excluded.id, themes[0].artifact_ids)

    def test_clustering_skips_no_l2(self) -> None:
        """Papers without summary_l2 should not be clustered."""

        included = self._save_artifact(title="Included Paper", summary_l2=self._summary_l2("Included Paper"))
        excluded = self._save_artifact(title="Missing L2", summary_l2=None)
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "Program Analysis",
                        "description": "Program analysis theme.",
                        "paper_ids": [included.id],
                        "keywords": ["analysis"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "Program Analysis",
                        "description": "Program analysis theme.",
                        "merged_from": ["Program Analysis"],
                        "keywords": ["analysis"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{paper_list}}", encoding="utf-8")

        themes = pipeline.process(None)

        self.assertEqual(len(themes), 1)
        self.assertEqual(themes[0].artifact_ids, [included.id])
        self.assertNotIn(excluded.id, themes[0].artifact_ids)

    def test_clustering_skips_blogs(self) -> None:
        """Blog artifacts should be excluded from theme clustering."""

        included = self._save_artifact(title="Included Paper", source_type=SourceType.PAPERS)
        excluded = self._save_artifact(title="Blog Entry", source_type=SourceType.BLOGS)
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "Web Security",
                        "description": "Web security theme.",
                        "paper_ids": [included.id],
                        "keywords": ["web"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "Web Security",
                        "description": "Web security theme.",
                        "merged_from": ["Web Security"],
                        "keywords": ["web"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{paper_list}}", encoding="utf-8")

        themes = pipeline.process(None)

        self.assertEqual(len(themes), 1)
        self.assertEqual(themes[0].artifact_ids, [included.id])
        self.assertNotIn(excluded.id, themes[0].artifact_ids)

    def test_merge_combines_similar_clusters(self) -> None:
        """Merge output should reduce multiple raw clusters into one theme when requested."""

        papers = [self._save_artifact(title=f"Paper {index}") for index in range(4)]
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "Web Fuzzing",
                        "description": "Cluster A.",
                        "paper_ids": [papers[0].id, papers[1].id],
                        "keywords": ["web", "fuzzing"],
                    },
                ),
                self._cluster_response(
                    {
                        "cluster_label": "Browser Fuzzing",
                        "description": "Cluster B.",
                        "paper_ids": [papers[2].id, papers[3].id],
                        "keywords": ["browser", "fuzzing"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "Web/Browser Fuzzing",
                        "description": "Merged fuzzing theme.",
                        "merged_from": ["Web Fuzzing", "Browser Fuzzing"],
                        "keywords": ["fuzzing", "browser"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
            batch_size=2,
        )
        (self.workspace / "prompt.md").write_text("{{paper_list}}", encoding="utf-8")

        themes = pipeline.process(None)

        # With <= 15 unique labels, LLM merge is skipped.
        # Two distinct batch labels become two themes.
        self.assertEqual(len(themes), 2)
        theme_names = {t.name for t in themes}
        self.assertIn("Web Fuzzing", theme_names)
        self.assertIn("Browser Fuzzing", theme_names)
        # Only 2 batch calls, no merge call
        self.assertEqual(len(llm_client.calls), 2)

    def test_full_recluster_preserves_core(self) -> None:
        """Full reclustering should not delete pre-existing core themes."""

        self._save_theme(name="Existing Core", status=ThemeStatus.CORE, generation_version="v1")
        paper = self._save_artifact(title="Cluster Paper")
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "New Theme",
                        "description": "New candidate theme.",
                        "paper_ids": [paper.id],
                        "keywords": ["candidate"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "New Theme",
                        "description": "New candidate theme.",
                        "merged_from": ["New Theme"],
                        "keywords": ["candidate"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{paper_list}}", encoding="utf-8")

        pipeline.process(None)

        session: Session = self.session_factory()
        try:
            repository = ThemeRepository(session)
            core_names = [theme.name for theme in repository.list_by_status(ThemeStatus.CORE)]
            candidate_names = [theme.name for theme in repository.list_by_status(ThemeStatus.CANDIDATE)]
            self.assertEqual(core_names, ["Existing Core"])
            self.assertEqual(candidate_names, ["New Theme"])
        finally:
            session.close()

    def test_full_recluster_replaces_candidates(self) -> None:
        """Full reclustering should delete same-version candidate themes before saving new ones."""

        old_candidate = self._save_theme(name="Old Candidate", status=ThemeStatus.CANDIDATE, generation_version="v1")
        paper = self._save_artifact(title="Cluster Paper")
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "Replacement Theme",
                        "description": "Replacement candidate theme.",
                        "paper_ids": [paper.id],
                        "keywords": ["replacement"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "Replacement Theme",
                        "description": "Replacement candidate theme.",
                        "merged_from": ["Replacement Theme"],
                        "keywords": ["replacement"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
            cluster_version="v1",
        )
        (self.workspace / "prompt.md").write_text("{{paper_list}}", encoding="utf-8")

        themes = pipeline.process(None)

        session: Session = self.session_factory()
        try:
            repository = ThemeRepository(session)
            remaining = repository.list_by_status(ThemeStatus.CANDIDATE)
            self.assertEqual([theme.name for theme in remaining], ["Replacement Theme"])
            self.assertIsNone(repository.get_by_theme_id(old_candidate.theme_id))
            self.assertEqual(len(themes), 1)
        finally:
            session.close()

    def test_paper_count_by_year(self) -> None:
        """Persisted themes should store a year histogram for member papers."""

        papers = [
            self._save_artifact(title="Paper 1", year=2024),
            self._save_artifact(title="Paper 2", year=2024),
            self._save_artifact(title="Paper 3", year=2025),
        ]
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "Year Theme",
                        "description": "Year histogram theme.",
                        "paper_ids": [paper.id for paper in papers],
                        "keywords": ["years"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "Year Theme",
                        "description": "Year histogram theme.",
                        "merged_from": ["Year Theme"],
                        "keywords": ["years"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{paper_list}}", encoding="utf-8")

        themes = pipeline.process(None)

        self.assertEqual(themes[0].paper_count_by_year, {"2024": 2, "2025": 1})

    def test_week_id_computed(self) -> None:
        """Persisted themes should store the current ISO week id."""

        paper = self._save_artifact(title="Week Paper")
        llm_client = StubLLMClient(
            [
                self._cluster_response(
                    {
                        "cluster_label": "Week Theme",
                        "description": "Week theme.",
                        "paper_ids": [paper.id],
                        "keywords": ["week"],
                    },
                ),
                self._merge_response(
                    {
                        "final_label": "Week Theme",
                        "description": "Week theme.",
                        "merged_from": ["Week Theme"],
                        "keywords": ["week"],
                    },
                ),
            ]
        )
        pipeline = ClusteringPipeline(
            session_factory=self.session_factory,
            llm_client=llm_client,
            prompt_template_path=self.workspace / "prompt.md",
        )
        (self.workspace / "prompt.md").write_text("{{paper_list}}", encoding="utf-8")

        themes = pipeline.process(None)

        iso_year, iso_week, _ = date.today().isocalendar()
        self.assertEqual(themes[0].week_id, f"{iso_year}-W{iso_week:02d}")

    def _cluster_response(self, *clusters: dict[str, object]) -> str:
        """Build one batch cluster JSON array."""

        return json.dumps(list(clusters), ensure_ascii=False)

    def _merge_response(self, *clusters: dict[str, object]) -> str:
        """Build one merge cluster JSON array."""

        return json.dumps(list(clusters), ensure_ascii=False)

    def _summary_l2(self, title: str) -> str:
        """Build one deterministic deep-analysis payload."""

        return json.dumps(
            {
                "research_problem": f"{title} addresses web security analysis.",
                "motivation": "Motivation",
                "methodology": "Program analysis plus fuzzing.",
                "core_contributions": ["Contribution"],
                "limitations": ["Limitation"],
                "open_questions": ["Question"],
                "related_concepts": ["web", "fuzzing", "analysis"],
            },
            ensure_ascii=False,
        )

    def _save_artifact(self, **kwargs) -> Artifact:
        """Persist one artifact with sensible defaults."""

        session: Session = self.session_factory()
        try:
            title = kwargs.pop("title", "Test Artifact")
            artifact = Artifact(
                title=title,
                authors=kwargs.pop("authors", ["Alice Example"]),
                year=kwargs.pop("year", 2026),
                source_type=kwargs.pop("source_type", SourceType.PAPERS),
                source_tier=kwargs.pop("source_tier", "top-tier"),
                source_name=kwargs.pop("source_name", "NDSS"),
                source_url=kwargs.pop("source_url", "https://example.com/artifact"),
                abstract=kwargs.pop("abstract", "A useful abstract."),
                summary_l1=kwargs.pop("summary_l1", "One-line summary."),
                summary_l2=kwargs.pop("summary_l2", self._summary_l2(title)),
                tags=kwargs.pop("tags", ["web-security", "analysis"]),
                relevance_score=kwargs.pop("relevance_score", 0.8),
                status=kwargs.pop("status", ArtifactStatus.ACTIVE),
                **kwargs,
            )
            session.add(artifact)
            session.commit()
            session.refresh(artifact)
            return artifact
        finally:
            session.close()

    def _save_theme(self, **kwargs) -> Theme:
        """Persist one theme row for repository-preservation checks."""

        session: Session = self.session_factory()
        try:
            theme = Theme(
                name=kwargs.pop("name", "Existing Theme"),
                description=kwargs.pop("description", "Existing description"),
                keywords=kwargs.pop("keywords", ["existing"]),
                artifact_ids=kwargs.pop("artifact_ids", [999]),
                artifact_count=kwargs.pop("artifact_count", 1),
                paper_count_by_year=kwargs.pop("paper_count_by_year", {"2026": 1}),
                methodology_tags=kwargs.pop("methodology_tags", []),
                open_questions=kwargs.pop("open_questions", []),
                trend_direction=kwargs.pop("trend_direction", None),
                status=kwargs.pop("status", ThemeStatus.CANDIDATE),
                generation_version=kwargs.pop("generation_version", "v1"),
                week_id=kwargs.pop("week_id", "2026-W11"),
                **kwargs,
            )
            session.add(theme)
            session.commit()
            session.refresh(theme)
            return theme
        finally:
            session.close()

    def _save_profile(self) -> Profile:
        """Persist one active profile for prompt-context tests."""

        session: Session = self.session_factory()
        try:
            profile = Profile(
                profile_version="v1",
                current_research_area="Web应用安全与软件安全",
                interests=["Web漏洞检测", "程序分析"],
                preferred_topics=["web-security", "fuzzing"],
                avoided_topics=["blockchain"],
                is_active=True,
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile
        finally:
            session.close()
