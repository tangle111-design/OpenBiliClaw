"""Tests for the Douyin direct-cookie discovery strategy."""

from __future__ import annotations

import pytest

from openbiliclaw.discovery.strategies.douyin_direct import DouyinDirectStrategy
from openbiliclaw.soul.profile import InterestTag, PreferenceLayer, SoulProfile


class _FakeDouyinClient:
    async def search_aweme(self, keyword: str, *, limit: int = 30) -> list[dict[str, object]]:
        return [{"aweme_id": "1", "desc": f"{keyword} 视频", "author": {"nickname": "A"}}]

    async def get_hot_board(self, *, limit: int = 30) -> list[dict[str, object]]:
        return [{"aweme_id": "2", "desc": "热点视频", "author": {"nickname": "B"}}]

    async def get_creator_posts(self, sec_uid: str, *, limit: int = 30) -> list[dict[str, object]]:
        return [{"aweme_id": "3", "desc": f"{sec_uid} 作者视频", "author": {"nickname": "C"}}]

    async def get_recommend_feed(self, *, limit: int = 30) -> list[dict[str, object]]:
        return [{"aweme_id": "4", "desc": "首页推荐视频", "author": {"nickname": "D"}}]


def _profile() -> SoulProfile:
    return SoulProfile(
        personality_portrait="喜欢理解复杂系统",
        core_traits=["理性", "好奇"],
        preferences=PreferenceLayer(
            interests=[
                InterestTag(name="机械键盘", category="科技", weight=0.9),
                InterestTag(name="城市观察", category="生活", weight=0.7),
            ]
        ),
    )


@pytest.mark.asyncio
async def test_strategy_returns_douyin_discovered_content() -> None:
    strategy = DouyinDirectStrategy(
        client=_FakeDouyinClient(),
        sources=("search", "hot", "creator"),
        seed_keywords=["机械键盘"],
        creator_sec_uids=["sec-1"],
        llm_evaluation=False,
    )

    items = await strategy.discover(_profile(), limit=10)

    assert {item.source_platform for item in items} == {"douyin"}
    assert {item.source_strategy for item in items} == {
        "dy-direct-search",
        "dy-direct-hot",
        "dy-direct-creator",
    }
    assert [item.content_id for item in items] == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_strategy_dedupes_before_returning() -> None:
    class DuplicateClient(_FakeDouyinClient):
        async def get_hot_board(self, *, limit: int = 30) -> list[dict[str, object]]:
            return [{"aweme_id": "1", "desc": "重复视频", "author": {"nickname": "B"}}]

    strategy = DouyinDirectStrategy(
        client=DuplicateClient(),
        sources=("search", "hot"),
        seed_keywords=["机械键盘"],
        llm_evaluation=False,
    )

    items = await strategy.discover(_profile(), limit=10)

    assert [item.content_id for item in items] == ["1"]


@pytest.mark.asyncio
async def test_strategy_uses_profile_interests_as_fallback_keywords() -> None:
    class RecordingClient(_FakeDouyinClient):
        def __init__(self) -> None:
            self.keywords: list[str] = []

        async def search_aweme(self, keyword: str, *, limit: int = 30) -> list[dict[str, object]]:
            self.keywords.append(keyword)
            return []

    client = RecordingClient()
    strategy = DouyinDirectStrategy(
        client=client,
        sources=("search",),
        seed_keywords=(),
        llm_evaluation=False,
    )

    await strategy.discover(_profile(), limit=10)

    assert client.keywords == ["机械键盘", "城市观察"]


@pytest.mark.asyncio
async def test_strategy_uses_client_search_source_strategy() -> None:
    class PluginSearchClient(_FakeDouyinClient):
        search_source_strategy = "dy-plugin-search"

    strategy = DouyinDirectStrategy(
        client=PluginSearchClient(),
        sources=("search",),
        seed_keywords=["机械键盘"],
        llm_evaluation=False,
    )

    items = await strategy.discover(_profile(), limit=10)

    assert [item.source_strategy for item in items] == ["dy-plugin-search"]


@pytest.mark.asyncio
async def test_strategy_uses_client_hot_source_strategy() -> None:
    class PluginHotClient(_FakeDouyinClient):
        hot_source_strategy = "dy-plugin-hot-related"

    strategy = DouyinDirectStrategy(
        client=PluginHotClient(),
        sources=("hot",),
        llm_evaluation=False,
    )

    items = await strategy.discover(_profile(), limit=10)

    assert [item.source_strategy for item in items] == ["dy-plugin-hot-related"]


@pytest.mark.asyncio
async def test_strategy_uses_client_feed_source_strategy() -> None:
    class PluginFeedClient(_FakeDouyinClient):
        feed_source_strategy = "dy-plugin-feed"

    strategy = DouyinDirectStrategy(
        client=PluginFeedClient(),
        sources=("feed",),
        llm_evaluation=False,
    )

    items = await strategy.discover(_profile(), limit=10)

    assert [item.source_strategy for item in items] == ["dy-plugin-feed"]
    assert [item.content_id for item in items] == ["4"]
