# 稍后再看 (Watch Later) — Feature Spec

## 1. 概述

本地书签功能，让用户在任意推荐 surface 上通过时钟按钮标记视频"稍后再看"，跨 surface 同步状态。

数据存储在本地 SQLite，不影响 soul profile 也不影响推荐评分。

## 2. 数据层

### 2.1 表结构

```sql
CREATE TABLE IF NOT EXISTS watch_later (
    bvid     TEXT PRIMARY KEY,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note     TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_watch_later_added
    ON watch_later(added_at DESC);
```

自动 migration：`_ensure_watch_later_table()` 在 DB 初始化时检查并创建。

### 2.2 DB 方法

| 方法 | 签名 | 说明 |
|------|------|------|
| `add_to_watch_later` | `(bvid: str, note: str = "") -> bool` | UPSERT，重复保存更新 `added_at` |
| `remove_from_watch_later` | `(bvid: str) -> bool` | 删除 |
| `is_in_watch_later` | `(bvid: str) -> bool` | 查询 |
| `count_watch_later` | `() -> int` | 总数 |
| `list_watch_later` | `(limit=50, offset=0) -> list[dict]` | 分页列表，JOIN content_cache 拿标题/封面/平台 |

## 3. API

| 端点 | 方法 | 请求体 | 响应 |
|------|------|--------|------|
| `/api/watch-later` | POST | `{bvid: str, note?: str}` | `WatchLaterStateResponse` |
| `/api/watch-later/{bvid}` | DELETE | — | `WatchLaterStateResponse` |
| `/api/watch-later/{bvid}` | GET | — | `WatchLaterStateResponse` |
| `/api/watch-later` | GET | `?limit=50&offset=0` | `WatchLaterListResponse` |

**WatchLaterStateResponse**: `{saved: bool, total: int}`

**WatchLaterListResponse**: `{items: WatchLaterItem[], total: int}`

**WatchLaterItem**: `{bvid, title, up_name, cover_url, content_url, source_platform, added_at}`

> 关联功能：「[收藏夹 (favorites)](favorites.md)」是与稍后再看互相独立的永久收藏集合，复用同一套浏览列表组件。

## 4. 前端 — 时钟 toggle + 浏览页

各 surface 的推荐卡和 delight 卡上有时钟 SVG toggle 按钮；已保存内容的浏览页现已在三端实现（见 §6）。

### 4.1 通用交互规范

- **稍后再看按钮**：时钟 SVG，点击 toggle；选中态通过 `aria-pressed=true` 与 accent 色表达
- **乐观 UI**：点击后立即切换图标，请求失败时回退
- **防抖**：同一 bvid 的并发请求用 busy flag 互斥
- **懒加载状态**：卡片渲染后异步查询 `GET /api/watch-later/{bvid}` 同步时钟状态

### 4.2 各 Surface 实现

| Surface | 推荐卡时钟位置 | Delight 卡时钟位置 | 懒加载 |
|---------|---------------|-------------------|--------|
| 插件 popup | 推荐卡动作行，与收藏星标并列 | delight banner 动作行，与收藏星标并列 | `watchLaterStatus()` + `popup-saved-sync.js` |
| 移动端 Web | 封面右上角 chip | delight tray 动作行，与收藏星标并列 | `watchLaterStatus()` + `watchLaterSaved` Set |
| 桌面端 Web | dismiss 按钮之后 | dismiss 按钮之后 | `requestJson` GET 回调 |

## 5. 不做的事情（scope out）

| 特性 | 原因 |
|------|------|
| Note 编辑 UI | 数据层已支持，UI 推迟 |
| 搜索/筛选 | 列表量级小，不需要 |
| "已看"归档 | 增加概念复杂度 |
| 与 B 站原生"稍后再看"同步 | scope 太大 |

## 6. 浏览页（已实现）

各 surface 提供已保存内容的浏览入口与列表（与[收藏夹](favorites.md)复用同一套列表组件）：

| Surface | 列表入口 | 列表 API |
|---------|----------|----------|
| 插件 popup | tab bar「稍后」页（`viewWatchLater` + `watchLaterList`） | `fetchWatchLater()` + `loadWatchLater()` |
| 移动端 Web | 底部导航「稍后」tab（`initWatchLaterView`） | `fetchWatchLater()` |
| 桌面端 Web | 侧边栏「稍后再看」(`watchLaterBtn` + `watchLaterPage` + `watchLaterCountBadge`) | `refreshWatchLater()` + `syncWatchLaterButtons()` |

列表项支持点击打开、单条移除；插件 popup 列表项会展示固定 16:9 头图缩略图，并复用 `/api/image-proxy` 加载封面。桌面端导航项带数量徽章。GET `/api/watch-later` 现已对 `limit/offset` 做 422 校验。
