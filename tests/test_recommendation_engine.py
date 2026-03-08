"""Tests for recommendation ranking engine."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openbiliclaw.discovery.engine import DiscoveredContent
from openbiliclaw.recommendation.engine import RecommendationEngine
from openbiliclaw.soul.profile import InterestTag, PreferenceLayer, SoulProfile
from openbiliclaw.storage.database import Database


class _DummyLLM:
    pass


def _build_profile() -> SoulProfile:
    return SoulProfile(
        personality_portrait="一个偏好高信息密度、慢热但判断稳定的人。",
        core_traits=["理性", "克制"],
        preferences=PreferenceLayer(
            interests=[InterestTag(name="纪录片", category="知识", weight=0.9)]
        ),
    )


@pytest.mark.asyncio
async def test_generate_recommendations_ranks_discovered_and_records_history() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "test.db")
        db.initialize()
        engine = RecommendationEngine(llm=_DummyLLM(), database=db)

        discovered = [
            DiscoveredContent(bvid="BV1A", title="A", relevance_score=0.71),
            DiscoveredContent(bvid="BV1B", title="B", relevance_score=0.92),
            DiscoveredContent(bvid="BV1C", title="C", relevance_score=0.83),
        ]

        recommendations = await engine.generate_recommendations(
            discovered=discovered,
            profile=_build_profile(),
            limit=2,
        )

        assert [item.content.bvid for item in recommendations] == ["BV1B", "BV1C"]
        assert recommendations[0].confidence == 0.92

        history = db.get_recommendations(limit=10)
        assert [row["bvid"] for row in history] == ["BV1C", "BV1B"]


@pytest.mark.asyncio
async def test_generate_recommendations_reads_from_cache_when_discovered_missing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "test.db")
        db.initialize()
        db.cache_content(
            "BV1A",
            title="A",
            up_name="UPA",
            source="search",
            view_count=10,
        )
        db.cache_content(
            "BV1B",
            title="B",
            up_name="UPB",
            source="search",
            view_count=20,
        )
        engine = RecommendationEngine(llm=_DummyLLM(), database=db)

        recommendations = await engine.generate_recommendations(
            discovered=None,
            profile=_build_profile(),
            limit=1,
        )

        assert [item.content.bvid for item in recommendations] == ["BV1B"]


@pytest.mark.asyncio
async def test_generate_recommendations_does_not_repeat_history() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db = Database(Path(tmpdir) / "test.db")
        db.initialize()
        db.cache_content(
            "BV1A",
            title="A",
            up_name="UPA",
            source="search",
            view_count=10,
        )
        db.cache_content(
            "BV1B",
            title="B",
            up_name="UPB",
            source="search",
            view_count=20,
        )
        engine = RecommendationEngine(llm=_DummyLLM(), database=db)

        first = await engine.generate_recommendations(
            discovered=None,
            profile=_build_profile(),
            limit=1,
        )
        second = await engine.generate_recommendations(
            discovered=None,
            profile=_build_profile(),
            limit=1,
        )

        assert [item.content.bvid for item in first] == ["BV1B"]
        assert [item.content.bvid for item in second] == ["BV1A"]
