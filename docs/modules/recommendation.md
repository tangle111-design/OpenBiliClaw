# 推荐引擎

> 从 discovery 缓存中挑出最值得推的内容，并逐步生成像朋友一样的推荐表达。

## 概述

`recommendation/` 包负责把已经发现并评分过的内容，转成真正准备展示给用户的推荐结果。

当前模块包含：

- **RecommendationEngine** — 推荐排序与推荐历史写入入口
- **Recommendation** — 单条推荐结果
- **PersonalTopic** — 后续个性化主题分组的占位结构

## 已实现功能

| 任务 | 状态 | 说明 |
|------|------|------|
| 6.1 推荐排序 | ✅ | 从 `content_cache` 选未推荐内容、按分数排序、写入推荐历史 |
| 6.2 朋友式推荐表达 | 🔲 | 未开始 |
| 6.3 推荐持久化 | 🔄 | 已有最小推荐历史写入，待补展示状态与反馈 |

## 公开 API

### RecommendationEngine

```python
from openbiliclaw.recommendation.engine import RecommendationEngine

engine = RecommendationEngine(llm=llm, database=db)
items = await engine.generate_recommendations(
    discovered=None,
    profile=profile,
    limit=5,
)
```

行为说明：

- 若传入 `discovered`，优先对该批内容排序
- 若未传入 `discovered`，从 `content_cache` 中读取未推荐内容
- 排序主键是 `relevance_score`，其次是 `view_count`
- 生成结果后会写入 `recommendations` 表，避免下次重复选中

### Recommendation

```python
Recommendation(
    content=content,
    confidence=0.87,
    presented=False,
)
```

当前 `6.1` 稳定填充的字段包括：

- `content`
- `confidence`
- `presented`

## 设计决策

1. **先做排序闭环，再做表达生成**：先确保“选谁”稳定，再讨论“怎么说”
2. **推荐历史在选中时写入**：避免相邻批次重复选择同一内容
3. **`presented` 先保持 `False`**：等 CLI 或插件真正展示时再更新展示状态
