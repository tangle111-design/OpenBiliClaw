"""Tests for the Soul-driven xhs search task producer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from openbiliclaw.runtime.xhs_producer import XhsTaskProducer
from openbiliclaw.soul.profile import (
    InterestDomain,
    InterestLayer,
    InterestSpecific,
    OnionProfile,
)
from openbiliclaw.sources.xhs_tasks import XhsTaskQueue
from openbiliclaw.storage.database import Database

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def db(tmp_path: Path) -> Database:
    d = Database(tmp_path / "producer.db")
    d.initialize()
    return d


@pytest.fixture
def queue(db: Database) -> XhsTaskQueue:
    return XhsTaskQueue(db)


def _profile_with_interests() -> OnionProfile:
    return OnionProfile(
        interest=InterestLayer(
            likes=[
                InterestDomain(
                    domain="机械键盘",
                    weight=0.9,
                    specifics=[InterestSpecific(name="客制化", weight=0.8)],
                ),
                InterestDomain(domain="咖啡", weight=0.7),
            ]
        )
    )


class _FakeSoulEngine:
    def __init__(self, profile: Any) -> None:
        self._profile = profile

    async def get_profile(self) -> Any:
        return self._profile


class _FakeLLMService:
    """Bypass the real LLM. ``generate_xhs_keywords`` is monkeypatched
    in tests, so this stub is never actually called — but the producer
    still type-checks against it."""

    async def complete_structured_task(self, **_kwargs: Any) -> Any:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_producer_skips_when_disabled(queue: XhsTaskQueue) -> None:
    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(_profile_with_interests()),
        llm_service=_FakeLLMService(),
        enabled=False,
    )
    result = await producer.produce_if_due()
    assert result == {"enqueued": 0, "attempted": 0, "reason": "disabled"}
    assert queue.next_pending() is None


@pytest.mark.asyncio
async def test_producer_enqueues_keywords_up_to_budget(
    queue: XhsTaskQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_keywords(_llm: Any, _profile: Any, *, count: int) -> list[str]:
        return [f"kw-{i}" for i in range(count)]

    monkeypatch.setattr(
        "openbiliclaw.runtime.xhs_producer.generate_xhs_keywords",
        fake_keywords,
    )

    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(_profile_with_interests()),
        llm_service=_FakeLLMService(),
        enabled=True,
        daily_budget=3,
        keywords_per_cycle=5,
        min_interval_hours=0,
    )
    result = await producer.produce_if_due()
    assert result["reason"] == "ok"
    assert result["enqueued"] == 3
    assert result["attempted"] == 5


@pytest.mark.asyncio
async def test_producer_limits_keyword_generation_to_requested_gap(
    queue: XhsTaskQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_counts: list[int] = []

    async def fake_keywords(_llm: Any, _profile: Any, *, count: int) -> list[str]:
        requested_counts.append(count)
        return [f"kw-{i}" for i in range(count)]

    monkeypatch.setattr(
        "openbiliclaw.runtime.xhs_producer.generate_xhs_keywords",
        fake_keywords,
    )

    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(_profile_with_interests()),
        llm_service=_FakeLLMService(),
        enabled=True,
        daily_budget=30,
        keywords_per_cycle=5,
        min_interval_hours=0,
    )
    result = await producer.produce_if_due(limit=2)

    assert requested_counts == [2]
    assert result["reason"] == "ok"
    assert result["attempted"] == 2
    assert result["enqueued"] == 2


@pytest.mark.asyncio
async def test_producer_throttled_when_recent_task_exists(
    queue: XhsTaskQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Seed a search task so the producer sees "recent activity"
    queue.enqueue("search", {"keyword": "existing"})

    async def fake_keywords(_llm: Any, _profile: Any, *, count: int) -> list[str]:
        return ["should-not-run"]

    monkeypatch.setattr(
        "openbiliclaw.runtime.xhs_producer.generate_xhs_keywords",
        fake_keywords,
    )

    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(_profile_with_interests()),
        llm_service=_FakeLLMService(),
        enabled=True,
        min_interval_hours=4,
    )
    result = await producer.produce_if_due()
    assert result["reason"] == "throttled"
    assert result["enqueued"] == 0


@pytest.mark.asyncio
async def test_producer_handles_empty_keywords(
    queue: XhsTaskQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_keywords(_llm: Any, _profile: Any, *, count: int) -> list[str]:
        return []

    monkeypatch.setattr(
        "openbiliclaw.runtime.xhs_producer.generate_xhs_keywords",
        fake_keywords,
    )

    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(_profile_with_interests()),
        llm_service=_FakeLLMService(),
        min_interval_hours=0,
    )
    result = await producer.produce_if_due()
    assert result["reason"] == "no_keywords"


@pytest.mark.asyncio
async def test_producer_handles_missing_profile(queue: XhsTaskQueue) -> None:
    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(None),
        llm_service=_FakeLLMService(),
        min_interval_hours=0,
    )
    result = await producer.produce_if_due()
    assert result["reason"] == "no_profile"


# ── P1.5 caller-supplied keyword injection ───────────────────────────


def _pending_search_keywords(db: Database) -> list[str]:
    rows = db.conn.execute(
        "SELECT payload_json FROM xhs_tasks WHERE type = 'search' ORDER BY created_at ASC, id ASC"
    ).fetchall()
    out: list[str] = []
    for row in rows:
        payload = json.loads(str(row[0]))
        out.append(str(payload.get("keyword", "")))
    return out


@pytest.mark.asyncio
async def test_producer_injected_keywords_skip_generation(
    db: Database,
    queue: XhsTaskQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_keywords(_llm: Any, _profile: Any, *, count: int) -> list[str]:
        nonlocal called
        called = True
        return ["should-not-run"]

    monkeypatch.setattr(
        "openbiliclaw.runtime.xhs_producer.generate_xhs_keywords",
        fake_keywords,
    )

    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(_profile_with_interests()),
        llm_service=_FakeLLMService(),
        enabled=True,
        min_interval_hours=0,
    )
    result = await producer.produce_if_due(keywords=["客制化键盘", "手冲咖啡"])

    assert result == {"enqueued": 2, "attempted": 2, "reason": "ok"}
    assert called is False  # injected keywords skip generate_xhs_keywords
    assert set(_pending_search_keywords(db)) == {"客制化键盘", "手冲咖啡"}


@pytest.mark.asyncio
async def test_producer_injected_keywords_dedupe_and_cap(
    db: Database,
    queue: XhsTaskQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_keywords(_llm: Any, _profile: Any, *, count: int) -> list[str]:
        raise AssertionError("should not be called")

    monkeypatch.setattr(
        "openbiliclaw.runtime.xhs_producer.generate_xhs_keywords",
        fake_keywords,
    )

    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(_profile_with_interests()),
        llm_service=_FakeLLMService(),
        enabled=True,
        keywords_per_cycle=2,
        min_interval_hours=0,
    )
    # 4 distinct after strip/dedupe, but keywords_per_cycle caps to 2 — so
    # only the first two survivors ("a", "b") are enqueued ("c" dropped).
    result = await producer.produce_if_due(
        keywords=["  a  ", "a", "", "b", "c"],
    )

    assert result["enqueued"] == 2
    # UUID task ids don't preserve insert order under SQL sort; assert the set.
    assert set(_pending_search_keywords(db)) == {"a", "b"}


@pytest.mark.asyncio
async def test_producer_injected_keywords_work_without_profile(
    db: Database,
    queue: XhsTaskQueue,
) -> None:
    # Injection bypasses the soul-profile fetch entirely (planner already
    # produced the keywords), so a missing profile is not a blocker.
    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(None),
        llm_service=_FakeLLMService(),
        enabled=True,
        min_interval_hours=0,
    )
    result = await producer.produce_if_due(keywords=["客制化键盘"])

    assert result["enqueued"] == 1
    assert _pending_search_keywords(db) == ["客制化键盘"]


@pytest.mark.asyncio
async def test_producer_empty_injected_keywords_is_no_keywords(
    queue: XhsTaskQueue,
) -> None:
    producer = XhsTaskProducer(
        task_queue=queue,
        soul_engine=_FakeSoulEngine(_profile_with_interests()),
        llm_service=_FakeLLMService(),
        enabled=True,
        min_interval_hours=0,
    )
    result = await producer.produce_if_due(keywords=["", "   "])

    assert result["reason"] == "no_keywords"
    assert result["enqueued"] == 0
