"""Tests for franchise extraction + dedup."""

from __future__ import annotations

from openbiliclaw.recommendation.franchise import (
    dedup_by_franchise,
    extract_franchise,
)


def test_extract_chinese_alias():
    assert extract_franchise("原神 4.0 须弥探索") == "原神"


def test_extract_world_name_maps_to_canonical_franchise():
    # "提瓦特" is the in-game world for 原神 — the user-reported case
    # where related_chain produced 5 提瓦特/蒙德/枫丹clips that all
    # need to collapse to a single franchise key.
    assert extract_franchise("提瓦特摄影集锦") == "原神"
    assert extract_franchise("蒙德 角色真实化") == "原神"
    assert extract_franchise("枫丹海域旅拍") == "原神"


def test_extract_english_alias_word_boundary():
    # "Genshin" should match in plain English title
    assert extract_franchise("Genshin Impact 4.5 trailer") == "原神"


def test_extract_roman_alias_avoids_false_positive_substrings():
    # Reaction words like "lol" must NOT match a franchise alias —
    # we deliberately don't carry "lol" as a 英雄联盟 alias because
    # the false positive rate would dwarf the true positives. Users
    # who care will say "英雄联盟" or "League of Legends" in title.
    assert extract_franchise("haha lol that was funny") is None
    # The full Chinese / English forms still resolve cleanly.
    assert extract_franchise("英雄联盟 全球总决赛") == "英雄联盟"
    assert extract_franchise("League of Legends finals") == "英雄联盟"


def test_extract_returns_none_for_unrelated_content():
    assert extract_franchise("如何 5 分钟做一份番茄炒蛋") is None
    assert extract_franchise("") is None


def test_extract_first_match_wins_in_declaration_order():
    # Title that contains both 原神 and an unrelated franchise term —
    # 原神 appears first in KNOWN_FRANCHISES so it wins.
    assert extract_franchise("原神 vs Minecraft 谁更好玩") == "原神"


def test_dedup_keeps_at_most_n_per_franchise():
    """Reproduces the user-reported case: 5 原神 in a row should
    collapse to ``max_per_franchise`` survivors, but unrelated content
    in between should not be touched."""
    rows = [
        {"id": 1, "title": "原神 4.0 须弥探索", "topic": "游戏"},
        {"id": 2, "title": "提瓦特 摄影集锦", "topic": "游戏摄影"},
        {"id": 3, "title": "如何 5 分钟做番茄炒蛋", "topic": "美食"},
        {"id": 4, "title": "蒙德 角色真实化", "topic": "人工智能"},
        {"id": 5, "title": "塞尔达 王国之泪 攻略", "topic": "游戏"},
        {"id": 6, "title": "枫丹海域旅拍", "topic": "游戏盘点"},
        {"id": 7, "title": "原神 AI 重制 2024", "topic": "游戏动漫"},
    ]
    out = dedup_by_franchise(rows, max_per_franchise=2)
    out_ids = [r["id"] for r in out]
    # First two 原神-related items survive (id=1, id=2); subsequent
    # 原神 items (id=4, id=6, id=7) are dropped. 塞尔达 (id=5) and
    # 美食 (id=3, no franchise) pass through untouched.
    assert out_ids == [1, 2, 3, 5]


def test_dedup_keeps_items_without_franchise():
    """Items without an extractable franchise should ALWAYS pass
    through — there's no constraint to apply."""
    rows = [
        {"id": 1, "title": "纯科普 如何看懂量子纠缠"},
        {"id": 2, "title": "如何 5 分钟做番茄炒蛋"},
        {"id": 3, "title": "城市观察局 上海弄堂"},
    ]
    out = dedup_by_franchise(rows, max_per_franchise=2)
    assert [r["id"] for r in out] == [1, 2, 3]


def test_dedup_zero_cap_returns_input_unchanged():
    """Defensive: max_per_franchise=0 disables the filter (escape hatch
    for ops who want to debug without deploying a code change)."""
    rows = [
        {"id": 1, "title": "原神 1"},
        {"id": 2, "title": "原神 2"},
        {"id": 3, "title": "原神 3"},
    ]
    assert len(dedup_by_franchise(rows, max_per_franchise=0)) == 3


def test_dedup_uses_topic_and_up_name_as_extra_signal():
    """A title that says nothing about the franchise but whose topic
    label or UP name does should still match. This is critical because
    the LLM sometimes promotes 'AI 重制' or 'AI 摄影' as the visible
    title with the actual IP only in the topic."""
    rows = [
        {"id": 1, "title": "AI 重制 经典场景", "topic": "原神"},
        {"id": 2, "title": "AI 重制 古风", "topic": "影视"},
        {"id": 3, "title": "幻想风景", "up_name": "原神官方"},
    ]
    out = dedup_by_franchise(rows, max_per_franchise=1)
    # id=1 matches via topic, id=3 matches via up_name → both 原神 → drop id=3
    # id=2 has no franchise → passes through
    out_ids = [r["id"] for r in out]
    assert out_ids == [1, 2]
