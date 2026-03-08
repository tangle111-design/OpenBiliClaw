"""Recommendation Engine — ranking, expression, and delivery.

Handles the final stage: taking discovered content and presenting it
to the user in a warm, friend-like manner with deep personal insights.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openbiliclaw.discovery.engine import DiscoveredContent
    from openbiliclaw.llm.base import LLMProvider
    from openbiliclaw.soul.profile import SoulProfile
    from openbiliclaw.storage.database import Database

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """A recommendation ready to present to the user."""

    content: DiscoveredContent
    expression: str = ""  # Friend-style recommendation reason
    topic_label: str = ""  # Personal topic (not generic categories)
    confidence: float = 0.0  # How confident the agent is in this rec
    presented: bool = False
    feedback: str | None = None  # User feedback after seeing it


@dataclass
class PersonalTopic:
    """A deeply personalized recommendation topic.

    Not generic labels like "Weekend Pack" but personal ones like:
    "你最近在探索摄影——这几个视频从你习惯的'搞明白原理'的角度讲构图"
    """

    title: str = ""
    description: str = ""
    recommendations: list[Recommendation] = field(default_factory=list)


class RecommendationEngine:
    """Produces warm, personalized recommendations.

    The engine takes discovered content and transforms it into
    friend-style recommendations with:
    - "我觉得" — subjective, personal judgment
    - "我理解你" — demonstrates deep understanding
    - Personal insights connecting content to the user's soul
    """

    def __init__(self, llm: LLMProvider, database: Database) -> None:
        self._llm = llm
        self._database = database

    async def generate_recommendations(
        self,
        discovered: list[DiscoveredContent] | None,
        profile: SoulProfile,
        limit: int = 10,
    ) -> list[Recommendation]:
        """Generate friend-style recommendations from discovered content.

        Args:
            discovered: Content discovered by the discovery engine.
            profile: User's soul profile for personalization.
            limit: Maximum number of recommendations.

        Returns:
            List of personalized recommendations.
        """
        candidates = (
            self._normalize_discovered(discovered)
            if discovered is not None
            else self._load_unrecommended_content(limit=max(limit * 3, 20))
        )
        ranked = sorted(
            candidates,
            key=lambda item: (-item.relevance_score, -item.view_count, item.bvid),
        )[:limit]

        recommendations = [
            Recommendation(
                content=item,
                confidence=item.relevance_score,
                presented=False,
            )
            for item in ranked
        ]
        for item in recommendations:
            self._database.insert_recommendation(
                item.content.bvid,
                confidence=item.confidence,
                expression=item.expression,
                topic=item.topic_label,
                presented=0,
            )
        return recommendations

    async def generate_personal_topic(
        self,
        recommendations: list[Recommendation],
        profile: SoulProfile,
    ) -> PersonalTopic:
        """Create a deeply personalized recommendation topic.

        The topic is unique to this user — not "周末放松包" but something
        that connects to their specific personality and current state.

        Args:
            recommendations: Recommendations to group into a topic.
            profile: User's soul profile.

        Returns:
            A PersonalTopic with a custom title and description.
        """
        # TODO: Use LLM to create a personal topic narrative
        return PersonalTopic()

    async def generate_expression(
        self,
        content: DiscoveredContent,
        profile: SoulProfile,
    ) -> str:
        """Generate a friend-style recommendation expression.

        The expression should feel like a close friend recommending something:
        warm, insightful, personal, with genuine understanding of why this
        specific person would enjoy this specific content.

        Args:
            content: The content being recommended.
            profile: User's soul profile.

        Returns:
            Natural language recommendation expression.
        """
        # TODO: Use LLM with soul context + content info
        return ""

    @staticmethod
    def _normalize_discovered(
        discovered: list[DiscoveredContent],
    ) -> list[DiscoveredContent]:
        return list(discovered)

    def _load_unrecommended_content(self, *, limit: int) -> list[DiscoveredContent]:
        from openbiliclaw.discovery.engine import DiscoveredContent

        rows = self._database.get_unrecommended_content(limit=limit)
        return [
            DiscoveredContent(
                bvid=str(row.get("bvid", "")),
                title=str(row.get("title", "")),
                up_name=str(row.get("up_name", "")),
                up_mid=int(row.get("up_mid", 0) or 0),
                duration=int(row.get("duration", 0) or 0),
                description=str(row.get("description", "")),
                cover_url=str(row.get("cover_url", "")),
                view_count=int(row.get("view_count", 0) or 0),
                like_count=int(row.get("like_count", 0) or 0),
                source_strategy=str(row.get("source", "")),
            )
            for row in rows
        ]
