"""Search-based content discovery strategy."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from openbiliclaw.discovery.engine import DiscoveredContent, DiscoveryStrategy

if TYPE_CHECKING:
    from openbiliclaw.soul.profile import SoulProfile

from openbiliclaw.llm.prompts import build_search_queries_prompt

logger = logging.getLogger(__name__)


class SupportsStructuredTask(Protocol):
    async def complete_structured_task(
        self,
        *,
        system_instruction: str,
        user_input: str,
        history: list[dict[str, str]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> object: ...


class SupportsSearchClient(Protocol):
    async def search(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20,
        order: str = "totalrank",
    ) -> list[dict[str, object]]: ...


@dataclass
class SearchStrategy(DiscoveryStrategy):
    """Discover content by generating search queries from user interests."""

    llm_service: SupportsStructuredTask
    bilibili_client: SupportsSearchClient
    queries_per_run: int = 8
    page_size: int = 10

    @property
    def name(self) -> str:
        return "search"

    async def discover(
        self, profile: SoulProfile, limit: int = 20
    ) -> list[DiscoveredContent]:
        """Generate search queries based on user soul and execute them.

        Strategy:
        1. Extract key interests from the soul profile
        2. Generate creative search keyword combinations
        3. Execute searches via Bilibili API
        4. Score results against the soul profile

        Args:
            profile: User soul profile.
            limit: Maximum results.

        Returns:
            Discovered content list.
        """
        queries = await self._generate_queries(profile)
        results: list[DiscoveredContent] = []
        seen_bvids: set[str] = set()

        for query_index, query in enumerate(queries):
            try:
                search_results = await self.bilibili_client.search(
                    query,
                    page=1,
                    page_size=self.page_size,
                )
            except Exception:
                logger.exception("Search query failed: %s", query)
                continue

            for item_index, item in enumerate(search_results):
                content = self._map_search_result(
                    item,
                    query_index=query_index,
                    item_index=item_index,
                )
                if content is None or content.bvid in seen_bvids:
                    continue
                seen_bvids.add(content.bvid)
                results.append(content)
                if len(results) >= limit:
                    return results

        return results

    async def _generate_queries(self, profile: SoulProfile) -> list[str]:
        prompt_messages = build_search_queries_prompt(
            profile_summary=self._profile_summary(profile)
        )
        try:
            response = await self.llm_service.complete_structured_task(
                system_instruction=prompt_messages[0]["content"],
                user_input=prompt_messages[1]["content"],
            )
            queries = self._parse_queries(str(getattr(response, "content", "")))
            if queries:
                return queries
        except Exception:
            logger.exception("Search query generation failed; falling back to local queries.")
        return self._fallback_queries(profile)

    def _parse_queries(self, content: str) -> list[str]:
        text = content.strip()
        if not text:
            return []
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return []
        raw_queries = parsed.get("queries", [])
        if not isinstance(raw_queries, list):
            return []
        queries: list[str] = []
        seen: set[str] = set()
        for item in raw_queries:
            query = str(item).strip()
            if not query or query in seen:
                continue
            seen.add(query)
            queries.append(query)
            if len(queries) >= min(self.queries_per_run, 10):
                break
        return queries

    def _fallback_queries(self, profile: SoulProfile) -> list[str]:
        queries: list[str] = []
        seen: set[str] = set()

        for interest in profile.preferences.interests:
            query = str(interest.name).strip()
            if not query or query in seen:
                continue
            seen.add(query)
            queries.append(query)
            if len(queries) >= min(self.queries_per_run, 5):
                return queries

        for trait in profile.core_traits:
            query = str(trait).strip()
            if not query or query in seen:
                continue
            seen.add(query)
            queries.append(query)
            if len(queries) >= min(self.queries_per_run, 5):
                break

        return queries

    @staticmethod
    def _profile_summary(profile: SoulProfile) -> dict[str, object]:
        return {
            "personality_portrait": profile.personality_portrait,
            "core_traits": profile.core_traits[:5],
            "interests": [
                {
                    "name": interest.name,
                    "category": interest.category,
                    "weight": interest.weight,
                }
                for interest in profile.preferences.interests[:10]
            ],
            "favorite_up_users": profile.preferences.favorite_up_users[:5],
            "deep_needs": profile.deep_needs[:5],
        }

    def _map_search_result(
        self,
        item: dict[str, object],
        *,
        query_index: int,
        item_index: int,
    ) -> DiscoveredContent | None:
        bvid = str(item.get("bvid", "")).strip()
        if not bvid:
            return None
        return DiscoveredContent(
            bvid=bvid,
            title=self._clean_text(str(item.get("title", ""))),
            up_name=self._clean_text(str(item.get("author", ""))),
            up_mid=self._to_int(item.get("mid", 0)),
            cover_url=str(item.get("pic", "")),
            duration=self._parse_duration(item.get("duration", 0)),
            view_count=self._to_int(item.get("play", 0)),
            description=self._clean_text(str(item.get("description", ""))),
            source_strategy=self.name,
            relevance_score=max(0.0, 0.2 - query_index * 0.02 - item_index * 0.005),
        )

    @staticmethod
    def _clean_text(value: str) -> str:
        return re.sub(r"<[^>]+>", "", value).strip()

    @staticmethod
    def _parse_duration(raw_value: object) -> int:
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, str) and ":" in raw_value:
            parts = [part for part in raw_value.split(":") if part.isdigit()]
            if len(parts) == 2:
                minutes, seconds = parts
                return int(minutes) * 60 + int(seconds)
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        return SearchStrategy._to_int(raw_value)

    @staticmethod
    def _to_int(raw_value: object) -> int:
        if isinstance(raw_value, bool):
            return int(raw_value)
        if isinstance(raw_value, int):
            return raw_value
        if isinstance(raw_value, float):
            return int(raw_value)
        if isinstance(raw_value, str):
            digits = raw_value.replace(",", "").strip()
            if digits.isdigit():
                return int(digits)
        return 0


class TrendingStrategy(DiscoveryStrategy):
    """Discover content from trending/ranking pages."""

    @property
    def name(self) -> str:
        return "trending"

    async def discover(
        self, profile: SoulProfile, limit: int = 20
    ) -> list[DiscoveredContent]:
        """Scan trending and ranking content, filter by soul relevance.

        Args:
            profile: User soul profile.
            limit: Maximum results.

        Returns:
            Discovered content list.
        """
        # TODO: Fetch trending/ranking from relevant categories
        # TODO: Filter by soul-based relevance
        return []


class RelatedChainStrategy(DiscoveryStrategy):
    """Discover content by following related recommendation chains."""

    @property
    def name(self) -> str:
        return "related_chain"

    async def discover(
        self, profile: SoulProfile, limit: int = 20
    ) -> list[DiscoveredContent]:
        """Start from known good content and explore related chains.

        Args:
            profile: User soul profile.
            limit: Maximum results.

        Returns:
            Discovered content list.
        """
        # TODO: Start from recently liked/high-rated content
        # TODO: Follow related recommendations iteratively
        # TODO: Score each step against soul profile
        return []


class ExploreStrategy(DiscoveryStrategy):
    """Cross-domain surprise discovery — find the unexpected."""

    @property
    def name(self) -> str:
        return "explore"

    async def discover(
        self, profile: SoulProfile, limit: int = 20
    ) -> list[DiscoveredContent]:
        """Deliberately explore domains the user hasn't tried.

        Uses the soul profile's deep needs and latent interests
        to hypothesize about what new domains might resonate.

        Args:
            profile: User soul profile.
            limit: Maximum results.

        Returns:
            Discovered content list.
        """
        # TODO: Use LLM to hypothesize new domain interests from soul
        # TODO: Search those domains
        # TODO: Score with extra weight for novelty
        return []
