"""Regression tests for mobile web view-model normalization helpers."""

from __future__ import annotations

import shutil
import subprocess
from textwrap import dedent

import pytest

_NODE = shutil.which("node")


def _run_js(script: str) -> subprocess.CompletedProcess[str]:
    assert _NODE, "node is required"
    return subprocess.run(
        [_NODE, "--input-type=module", "-e", script],
        cwd=".",
        text=True,
        capture_output=True,
        check=False,
    )


def _assert_js(script: str) -> None:
    result = _run_js(script)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(_NODE is None, reason="node is required for mobile web JS view-model tests")
class TestMobileWebViewModels:
    """Phase 1 view-model coverage."""

    def test_existing_helpers_still_work(self) -> None:
        """Backward compat: normalizePoolStatus, normalizeMbtiDimensions, normalizeChatTurn, normalizeCoverUrl, getCoverImageAttrs."""
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import {
              getCoverImageAttrs, normalizeChatTurn, normalizeCoverUrl,
              normalizeMbtiDimensions, normalizePoolStatus,
            } from "./src/openbiliclaw/web/js/view-models.js";

            assert.deepEqual(
              normalizePoolStatus({
                pool_available_count: 561,
                last_replenished_count: 1,
                recent_pool_topics: ["相关推荐", "站内热榜"],
              }),
              { pool_size: 561, recent_replenish: 1, current_topic: "相关推荐" },
            );

            assert.deepEqual(
              normalizeMbtiDimensions({
                type: "INTJ",
                dimensions: {
                  EI: { pole: "I", strength: 0.8 },
                  SN: { pole: "N", strength: 0.6 },
                },
              }),
              [
                { left: "E", right: "I", score: 0.9 },
                { left: "S", right: "N", score: 0.8 },
              ],
            );

            assert.equal(
              normalizeChatTurn({ turn_id: "m-1", message: "ping", reply: "pong", status: "completed" }).response,
              "pong",
            );

            assert.equal(normalizeCoverUrl("http://i2.hdslb.com/bfs/archive/demo.jpg"), "https://i2.hdslb.com/bfs/archive/demo.jpg");
            assert.equal(normalizeCoverUrl("//i1.hdslb.com/bfs/archive/demo.jpg"), "https://i1.hdslb.com/bfs/archive/demo.jpg");
            assert.equal(normalizeCoverUrl("https://sns-webpic-qc.xhscdn.com/demo.jpg"), "");
            assert.deepEqual(
              getCoverImageAttrs("https://i1.hdslb.com/bfs/archive/demo.jpg"),
              { src: "https://i1.hdslb.com/bfs/archive/demo.jpg", referrerPolicy: "no-referrer" },
            );
        """))

    def test_export_presence(self) -> None:
        """All Phase 1 helpers are exported."""
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import * as vm from "./src/openbiliclaw/web/js/view-models.js";

            const required = [
              "buildVideoUrl", "buildContentUrl",
              "normalizeRecommendation", "normalizeDelightCandidate",
              "getDelightUiState", "getDelightActionState",
              "buildFeedbackPayload", "validateCommentInput", "getCommentSubmitUiState",
              "normalizeProfileSummary", "normalizeCognitionUpdateCard",
              "buildNextCognitionHistoryState",
              "normalizeActivityFeed", "getActivityCardState",
              "getPoolStatusSummary", "normalizeRuntimeStatus", "mergeRuntimeStatusEvent",
              "getReadyRecommendationHint",
              "formatRelativeTimestamp",
              "normalizeSourcePlatform", "getSourceLabel",
              "normalizeCoverUrl", "getCoverImageAttrs",
              "normalizePoolStatus", "normalizeMbtiDimensions", "normalizeChatTurn",
            ];
            for (const name of required) {
              assert.equal(typeof vm[name], "function", `missing export: ${name}`);
            }
        """))

    def test_normalize_recommendation_defaults(self) -> None:
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { normalizeRecommendation } from "./src/openbiliclaw/web/js/view-models.js";

            const rec = normalizeRecommendation({ id: 42, bvid: "BV1xx" });
            assert.equal(rec.id, 42);
            assert.equal(rec.bvid, "BV1xx");
            assert.equal(rec.title, "这条标题还没对上号");
            assert.equal(rec.up_name, "这位 UP 还没认出来");
            assert.equal(rec.source_platform, "bilibili");
        """))

    def test_build_feedback_payload(self) -> None:
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { buildFeedbackPayload } from "./src/openbiliclaw/web/js/view-models.js";

            const p = buildFeedbackPayload(42, "like", "  nice  ");
            assert.equal(p.recommendation_id, 42);
            assert.equal(p.feedback_type, "like");
            assert.equal(p.note, "nice");

            const p2 = buildFeedbackPayload("99", "comment");
            assert.equal(p2.recommendation_id, 99);
            assert.equal(p2.note, "");
        """))

    def test_delight_action_state(self) -> None:
        """getDelightActionState maps UI actions to backend-safe API tokens."""
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { getDelightActionState } from "./src/openbiliclaw/web/js/view-models.js";

            const view = getDelightActionState("view");
            assert.equal(view.apiResponse, "view");
            assert.equal(view.uiState, "viewed");
            assert.equal(view.permanent, true);

            const reject = getDelightActionState("reject");
            assert.equal(reject.apiResponse, "dislike");
            assert.equal(reject.uiState, "rejected");
            assert.equal(reject.permanent, true);

            const chat = getDelightActionState("chat");
            assert.equal(chat.apiResponse, null);
            assert.equal(chat.uiState, "chatting");
            assert.equal(chat.permanent, false);

            const later = getDelightActionState("later");
            assert.equal(later.apiResponse, null);
            assert.equal(later.uiState, "pending");
            assert.equal(later.permanent, false);
        """))

    def test_delight_ui_state(self) -> None:
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { getDelightUiState } from "./src/openbiliclaw/web/js/view-models.js";

            const pending = getDelightUiState({ bvid: "BV1", title: "t", delight_score: 0.9 });
            assert.equal(pending.visible, true);
            assert.equal(pending.handled, false);
            assert.equal(pending.score_label, "大概率会戳中你");

            const viewed = getDelightUiState({ bvid: "BV1", state: "viewed", delight_score: 0.7 });
            assert.equal(viewed.handled, true);
            assert.equal(viewed.response_tone, "success");

            const empty = getDelightUiState({});
            assert.equal(empty.visible, false);
        """))

    def test_pool_status_summary_semantic(self) -> None:
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { getPoolStatusSummary } from "./src/openbiliclaw/web/js/view-models.js";

            // Uninit returns null
            assert.equal(getPoolStatusSummary({}), null);

            // Running with items
            const running = getPoolStatusSummary({
              initialized: true,
              pool_available_count: 20,
              pool_target_count: 30,
              manual_refresh_state: "running",
            });
            assert.equal(running.available, "还有 20 条可换");
            assert.equal(running.replenished, "后台继续在找更多");

            // Idle with recent replenish
            const idle = getPoolStatusSummary({
              initialized: true,
              pool_available_count: 34,
              pool_target_count: 30,
              last_replenished_count: 6,
              recent_pool_topics: ["游戏", "编程"],
              manual_refresh_state: "idle",
            });
            assert.equal(idle.available, "还有 34 条可换");
            assert.equal(idle.replenished, "刚补进 6 条");
            assert.equal(idle.topics, "游戏 / 编程");
        """))

    def test_normalize_activity_feed(self) -> None:
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { normalizeActivityFeed, getActivityCardState } from "./src/openbiliclaw/web/js/view-models.js";

            const empty = normalizeActivityFeed({});
            assert.equal(empty.items.length, 0);
            assert.equal(empty.live_summary, "");

            const feed = normalizeActivityFeed({
              live_summary: "正在补货",
              items: [{ id: "1", summary: "找到了3条", created_at: "2025-01-01" }],
              has_more: true,
              next_cursor: "abc",
            });
            assert.equal(feed.items.length, 1);
            assert.equal(feed.live_summary, "正在补货");
            assert.equal(feed.has_more, true);

            const card = getActivityCardState({ feed, expanded: false });
            assert.equal(card.line1, "正在补货");
            assert.equal(card.expanded, false);
        """))

    def test_normalize_profile_summary(self) -> None:
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { normalizeProfileSummary } from "./src/openbiliclaw/web/js/view-models.js";

            // Empty input gives defaults
            const empty = normalizeProfileSummary({});
            assert.equal(empty.initialized, false);
            assert.equal(empty.personality_portrait, "画像还在慢慢攒，先多看一阵。");
            assert.deepEqual(empty.core_traits, []);
            assert.deepEqual(empty.values, []);
            assert.equal(empty.exploration_openness, 0.5);

            // Full input
            const full = normalizeProfileSummary({
              initialized: true,
              personality_portrait: "test portrait",
              core_traits: ["curious", "  "],
              values: ["truth"],
              likes: [{ domain: "tech", weight: 0.8, specifics: [{ name: "AI" }] }],
              exploration_openness: 0.7,
              favorite_up_users: ["UP1"],
              speculative_interests: [{ domain: "cooking", confidence: 0.6, status: "active" }],
            });
            assert.equal(full.initialized, true);
            assert.equal(full.personality_portrait, "test portrait");
            assert.deepEqual(full.core_traits, ["curious"]);
            assert.equal(full.likes.length, 1);
            assert.equal(full.likes[0].specifics[0].name, "AI");
            assert.equal(full.exploration_openness, 0.7);
            assert.deepEqual(full.favorite_up_users, ["UP1"]);
            assert.equal(full.speculative_interests[0].domain, "cooking");
        """))

    def test_format_relative_timestamp(self) -> None:
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { formatRelativeTimestamp } from "./src/openbiliclaw/web/js/view-models.js";

            const now = Date.parse("2025-06-01T12:00:00Z");
            assert.equal(formatRelativeTimestamp("2025-06-01T11:59:30Z", now), "刚刚");
            assert.equal(formatRelativeTimestamp("2025-06-01T11:48:00Z", now), "12 分钟前");
            assert.equal(formatRelativeTimestamp("2025-06-01T09:00:00Z", now), "3 小时前");
            assert.equal(formatRelativeTimestamp("2025-05-30T12:00:00Z", now), "2 天前");
            assert.equal(formatRelativeTimestamp(""), "");
            assert.equal(formatRelativeTimestamp("not-a-date"), "");
        """))

    def test_source_platform_and_label(self) -> None:
        _assert_js(dedent("""
            import assert from "node:assert/strict";
            import { normalizeSourcePlatform, getSourceLabel } from "./src/openbiliclaw/web/js/view-models.js";

            assert.equal(normalizeSourcePlatform({ bvid: "BV1xx" }), "bilibili");
            assert.equal(normalizeSourcePlatform({ content_url: "https://www.youtube.com/watch?v=abc" }), "youtube");
            assert.equal(normalizeSourcePlatform({ source_platform: "douyin" }), "douyin");
            assert.equal(getSourceLabel("bilibili"), "Bilibili");
            assert.equal(getSourceLabel("youtube"), "YouTube");
            assert.equal(getSourceLabel("unknown"), "unknown");
        """))
