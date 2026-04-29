"""Heuristic franchise / IP key extraction.

Why this exists
---------------
Field reports show a single ``recommendation_click`` on, say,
"AI 重绘原神地图" cascading into a popup full of 原神 / 提瓦特 / 蒙德
videos. The cascade has multiple causes:

  1. The preference analyzer over-generalises one click into a strong
     franchise-level interest (e.g. ``原神 weight=0.6``).
  2. ``RelatedChainStrategy`` follows the seed video down related-video
     chains and produces five neighboring 原神 items.
  3. The recommendation engine only de-duplicates by ``topic_group`` /
     ``topic_key`` — both of which the LLM happily splits into
     "游戏", "游戏动漫", "人工智能", "游戏摄影", "游戏盘点" etc.,
     letting one IP slip through under five different group labels.
  4. ``/api/recommendations`` is a thin ``LIMIT 20`` over the latest
     rows with no final diversity pass.
  5. Disliking one 原神 video records ``topic_key`` only, so the
     franchise itself is never down-weighted.

The proper fix is to add a first-class ``franchise_key`` column on
``content_cache`` populated by the LLM evaluator. That's a larger
refactor. This module is the minimum viable layer that lives entirely
in title-string heuristics and unblocks the worst user-visible cases:

  * Final dedup in ``/api/recommendations`` — capped at
    ``max_per_franchise`` slots per IP within the returned window.
  * Dislike propagation in
    :class:`openbiliclaw.recommendation.curator.PoolCurator` — when the
    user dislikes one 原神 video, the curator down-weights other items
    whose title contains the same franchise.

Adding a franchise
------------------
``KNOWN_FRANCHISES`` is a flat list of ``(canonical_name, aliases)``.
The first alias hit on a substring match returns ``canonical_name``.
Aliases are case-insensitive; both Chinese and Roman names are listed
so titles with bilingual mixes (e.g. "Genshin / 原神 …") collapse to
the same key.

The list is intentionally short — only IPs we've actually seen
oversaturate a single popup. Adding everything tagged on the
recommendation feed would over-fire and start filtering legitimate
content. If your timeline reports a problem IP, add it here.
"""

from __future__ import annotations

import re

# Canonical name → list of substrings that map to it. All matching is
# case-insensitive. Chinese substrings should NOT have surrounding
# whitespace requirements (they often appear adjacent to other CJK
# characters); Roman aliases use ``\b`` word boundaries to avoid
# false positives like "ZZZ" matching every "buzzzz".
KNOWN_FRANCHISES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "原神",
        (
            "原神",  # title text
            "提瓦特",  # in-game world
            "蒙德",  # in-game region
            "璃月",
            "稻妻",
            "须弥",
            "枫丹",
            "纳塔",
            "至冬",
            "genshin",
        ),
    ),
    (
        "崩坏:星穹铁道",
        ("星穹铁道", "崩铁", "honkai star rail", "honkai: star rail", "hsr"),
    ),
    (
        "崩坏3",
        ("崩坏3", "崩崩崩", "honkai impact"),
    ),
    (
        "绝区零",
        ("绝区零", "zenless zone zero", "zzz"),
    ),
    (
        "鸣潮",
        ("鸣潮", "wuthering waves"),
    ),
    (
        "明日方舟",
        ("明日方舟", "arknights"),
    ),
    (
        "黑神话:悟空",
        ("黑神话", "黑神话悟空", "black myth", "wukong"),
    ),
    (
        "塞尔达传说",
        ("塞尔达", "zelda"),
    ),
    (
        "我的世界",
        ("我的世界", "minecraft", "mc 生存", "mc 红石"),
    ),
    (
        "Apex英雄",
        ("apex 英雄", "apex legends"),
    ),
    (
        "英雄联盟",
        # No bare "lol" — it's a reaction word that would collide with
        # untold numbers of unrelated titles. Stick to unambiguous forms.
        ("英雄联盟", "league of legends"),
    ),
    (
        "ChatGPT",
        ("chatgpt", "gpt-4", "gpt-5", "openai"),
    ),
    (
        "DeepSeek",
        ("deepseek", "ds-v3", "ds-v4"),
    ),
)


# Pre-compile alias → canonical lookup. CJK aliases are matched as
# bare substrings; Roman-only aliases get word boundaries so we don't
# match every word containing "lol" or "zzz".
_ROMAN_ONLY = re.compile(r"^[\x00-\x7f\s]+$")


def _alias_pattern(alias: str) -> re.Pattern[str]:
    if _ROMAN_ONLY.match(alias):
        return re.compile(rf"\b{re.escape(alias.lower())}\b")
    return re.compile(re.escape(alias))


_COMPILED: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (canonical, tuple(_alias_pattern(a) for a in aliases))
    for canonical, aliases in KNOWN_FRANCHISES
)


def extract_franchise(*texts: str) -> str | None:
    """Return the canonical franchise name for the first matching alias.

    Accepts any number of fields (title, topic_label, up_name, …). All
    fields are concatenated lower-cased and scanned in
    ``KNOWN_FRANCHISES`` declaration order. The order matters for
    ambiguous cases — e.g. listing ``崩坏:星穹铁道`` before ``崩坏3``
    means a video titled "崩坏:星穹铁道 v 崩坏3" returns the more
    specific franchise.

    Returns None when no franchise matches. Callers should treat
    None as "no constraint" — the dedup / penalty logic should
    only fire on a positive franchise hit.
    """
    haystack = " ".join(t for t in texts if t).lower()
    if not haystack:
        return None
    for canonical, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(haystack):
                return canonical
    return None


def dedup_by_franchise(
    rows: list[dict[str, object]],
    *,
    max_per_franchise: int = 2,
    title_field: str = "title",
    topic_field: str = "topic",
    up_field: str = "up_name",
) -> list[dict[str, object]]:
    """Drop later duplicates of the same franchise from a recommendation list.

    Stable order — preserves relative ordering of the items that survive.
    Items without a detectable franchise are kept as-is (no constraint).

    ``max_per_franchise`` is the per-window cap. With the popup typically
    rendering 20 items, ``max_per_franchise=2`` cuts the worst case (5
    原神 in a row) down to "at most 2 视觉相邻 originals + the rest are
    truly different".
    """
    if max_per_franchise <= 0:
        return list(rows)

    seen: dict[str, int] = {}
    survivors: list[dict[str, object]] = []
    for row in rows:
        franchise = extract_franchise(
            str(row.get(title_field, "")),
            str(row.get(topic_field, "")),
            str(row.get(up_field, "")),
        )
        if franchise is None:
            survivors.append(row)
            continue
        if seen.get(franchise, 0) >= max_per_franchise:
            continue
        seen[franchise] = seen.get(franchise, 0) + 1
        survivors.append(row)
    return survivors
