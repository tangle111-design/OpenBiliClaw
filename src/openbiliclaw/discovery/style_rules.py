"""Style classification rules for discovered content.

Defines token-based rules mapping content titles/descriptions to style keys.
Style keys are used downstream for diversity control in the candidate pool.
"""

from __future__ import annotations

# Ordered list of (style_key, token_tuple) — first match wins.
STYLE_RULES: list[tuple[str, tuple[str, ...]]] = [
    # 知识/信息类
    ("deep_dive", (
        "讲透", "底层逻辑", "为什么", "如何诞生", "实验经济学",
        "科幻", "定理", "理论", "原理", "解析",
        "原型", "战力系统",
        "哲学", "控制论", "混沌", "自组织", "世界观", "设定",
        "悖论", "逻辑谜题", "谜题", "存在主义", "形而上",
    )),
    ("tech_analysis", (
        "大模型", "人工智能", "芯片", "显微镜", "纳米",
        "编译器", "算法", "架构", "gpu", "cpu", "内核",
    )),
    ("news_brief", (
        "突发", "最新", "局势", "锐评", "发布", "快讯", "回应", "自焚",
    )),
    ("sci_fact", (
        "冷知识", "趣味", "事实", "奇怪", "不可思议", "惊人", "你知道吗",
    )),
    # 教程/指南类
    ("practical_guide", (
        "教程", "入门", "购买前", "怎么做", "建议", "指南", "统计", "课程",
        "导论", "从零开始", "原理图解", "数学原理", "透彻理解", "一小时从",
    )),
    ("tutorial_short", (
        "技巧", "速刷", "秒懂", "一学就会", "一招", "诀窍",
    )),
    # 故事/叙事类
    ("story_doc", (
        "纪录片", "纪录", "故事", "电影", "小说史", "讲了一个怎样", "短片",
        "全过程", "制造过程", "工艺难度", "设计面面观",
    )),
    ("emotional_narrative", (
        "治愈", "情感", "催泪", "泪目", "温暖", "人生", "真实故事",
    )),
    ("true_crime", (
        "案件", "命案", "悬案", "破案", "凶杀", "罪犯", "警局", "侦探",
    )),
    # 观点/评论类
    ("opinion_stand", (
        "观点", "评论", "立场", "我觉得", "分析", "看法", "锐评",
    )),
    ("review_roundup", (
        "盘点", "测评", "推荐", "合集", "排行", "top", "年度",
    )),
    # 生活/日常类
    ("lifestyle", (
        "日常", "vlog", "生活", "开箱", "房间", "一天", "routine",
    )),
    ("light_chat", (
        "闲聊", "杂谈", "聊天", "聊聊", "对话", "访谈",
    )),
    ("unboxing_experience", (
        "开箱", "体验", "第一视角", "上手", "试玩", "测评",
    )),
    # 视觉/艺术类
    ("visual_showcase", (
        "空镜", "混剪", "素材", "视觉", "厨向mad",
    )),
    # 游戏类
    ("game_strategy", (
        "攻略", "机制", "强度", "实机", "联机", "mod", "杀戮尖塔", "爬塔",
    )),
    # 音频/音乐类
    ("audio_background", (
        "背景音乐", "陪伴", "轻音乐", "学习音乐", "专注", "白噪音",
    )),
    ("music_live", (
        "演唱会", "live", "现场", "演出", "音乐节",
    )),
    ("music_analysis", (
        "乐理", "编曲", "和声", "和弦", "作曲", "音阶", "调式",
    )),
    # 娱乐/搞笑类
    ("fun_variety", (
        "搞笑", "吐槽", "整活", "挑战", "名场面", "鬼畜", "恶搞", "沙雕",
    )),
    ("live_moment", (
        "直播", "切片", "互动", "弹幕", "主播",
    )),
    ("parody_remix", (
        "二创", "翻唱", "配音", "模仿", "翻配", "混音",
    )),
    ("sports_highlight", (
        "集锦", "进球", "精彩", "高光", "绝杀", "得分",
    )),
]

# Fallback rules when no token matches — keyed by source_strategy.
# Note: explore intentionally has no fallback to avoid collapsing all
# cross-domain results into the same style bucket (hurts diversity).
SOURCE_FALLBACKS: dict[str, str] = {
    "trending": "news_brief",
}

DEFAULT_STYLE: str = "light_chat"


def infer_style_key(
    *,
    title: str,
    description: str = "",
    reason: str = "",
    source_strategy: str = "",
) -> str:
    """Infer a style_key from content text using rule-based token matching."""
    text = " ".join([title, description, reason]).lower()

    for style_key, tokens in STYLE_RULES:
        if any(token in text for token in tokens):
            return style_key

    fallback = SOURCE_FALLBACKS.get(source_strategy)
    if fallback:
        return fallback

    return DEFAULT_STYLE
