"""Tests for discovery engine orchestration."""

from __future__ import annotations

import pytest

from openbiliclaw.discovery.engine import ContentDiscoveryEngine
from openbiliclaw.soul.profile import SoulProfile

from .test_search_strategy import FakeBilibiliClient, FakeLLMService, _build_profile


@pytest.mark.asyncio
async def test_discovery_engine_runs_registered_search_strategy() -> None:
    from openbiliclaw.discovery.strategies.strategies import SearchStrategy

    engine = ContentDiscoveryEngine()
    strategy = SearchStrategy(
        llm_service=FakeLLMService('{"queries": ["纪录片 原理"]}'),
        bilibili_client=FakeBilibiliClient(
            {
                "纪录片 原理": [
                    {"bvid": "BV1A", "title": "纪录片", "author": "UP1", "mid": 1}
                ]
            }
        ),
    )
    engine.register_strategy(strategy)

    results = await engine.discover(_build_profile())

    assert len(results) == 1
    assert results[0].bvid == "BV1A"
    assert results[0].source_strategy == "search"


@pytest.mark.asyncio
async def test_discovery_engine_handles_empty_strategy_results() -> None:
    from openbiliclaw.discovery.strategies.strategies import SearchStrategy

    engine = ContentDiscoveryEngine()
    engine.register_strategy(
        SearchStrategy(
            llm_service=FakeLLMService('{"queries": []}'),
            bilibili_client=FakeBilibiliClient({}),
        )
    )

    results = await engine.discover(SoulProfile())

    assert results == []
