# Guided Init Module

## 概述

引导初始化（guided init）让用户既能在命令行 `openbiliclaw init`、也能在浏览器插件「推荐」tab 点「开始初始化」完成首轮建模。两条入口共用同一套四阶段流水线，后端再叠加进度状态机、前置检查和写者门控，保证图形化初始化在一个活跃后端上安全运行。

四阶段（与 CLI 完全一致）：

1. **拉取数据** — B站 历史 / 收藏 / 关注（`_fetch_bilibili_init_data`）+ 小红书 / 抖音 / YouTube bootstrap 信号采集（按启用平台）→ 统一 `build_event` → `memory.propagate_event` 入库。
2. **分析偏好** — `soul_engine.analyze_events(...)` 分片并发。
3. **生成画像** ‖ 4. **发现补池**（并行）— `soul_engine.build_initial_profile(...)` 与发现补池同时跑，发现用 preference-only 草稿画像预热评估。

## 共享流水线 `cli.run_guided_init`

| 项 | 说明 |
|---|---|
| 位置 | `src/openbiliclaw/cli.py` |
| 签名 | `async run_guided_init(*, client, memory, soul_engine, favorite_limit, follow_limit, include_xhs, include_dy, include_yt, target_pool_count, discover_backfill, coordinator=None, run_id=None) -> InitResult` |
| 为什么是协程 | 四阶段原先内联在 `init` 命令里，被四处独立 `asyncio.run` 包着，后端无法复用（会嵌套事件循环）。合并为一个协程后，CLI 用单次 `asyncio.run(run_guided_init(...))` 驱动、API 在服务 loop 里直接 `await`。 |
| bootstrap 采集器 | 仍是同步实现（有同步调用方 + 测试），但在流水线里走 `await asyncio.to_thread(...)`，不冻结 API 事件循环；`Database` 以 `check_same_thread=False` 打开，跨线程读安全。 |
| `discover_backfill` 注入 | 唯一与运行路径相关的步骤。CLI 传 `_run_init_discovery_backfill_async`（一次性 `discovery_engine`）；API 传 `controller.run_init_backfill`（持 `_refresh_lock`，与连续 refresh 串行）。其余步骤完全共享。 |
| 进度上报 | 传入 `coordinator` / `run_id` 时，在每个 stage 边界回调 `coordinator.stage_started/stage_done`、并 `register_enqueued_task` 登记 bootstrap task id；run 生命周期（mark_running / complete / fail）留给调用方。 |
| 失败语义 | 硬失败抛 `GuidedInitError(reason)`（`empty_history` / `profile_failed`）：CLI 转状态面板 + 退出码 1，API 转 `coordinator.fail(reason)`。发现阶段失败是部分成功（画像已生成），记在 `InitResult.discovery_error`。 |

`InitResult` 携带 CLI summary / API wrapper 需要的全部字段（各来源事件数、scope counts、profile、discovered_count、discovery_error）。

## 状态机 `InitCoordinator`

| 项 | 说明 |
|---|---|
| 位置 | `runtime/init_coordinator.py`；惰性挂在 `RuntimeContext.init_coordinator`（重建后仍读当前组件） |
| 持久化 | `init_runs` 表（`storage/database.py`）：`run_id / status / stage / stages_json / partial_success / error_reason / sequence / started_at / updated_at / finished_at` |
| 单飞启动 | `try_start(run_id)` → `try_reserve_init_starting`（`BEGIN IMMEDIATE` CAS）；活跃 run 存在时返回 False。TOCTOU 收口在 DB。 |
| 单写者 | `_write(...)` 在 `_write_lock` 下串行化「读 stages → 改 → 写 → 发事件」，保证并行 stage 3/4 的 `sequence` 严格递增、不丢更新。 |
| 事件 | `init_progress`（stage 起止）/ `init_completed` / `init_failed`，经 `event_hub` 推到 `runtime-stream`。 |
| 取消 | `attach_task` 记任务句柄；`cancel_current_run` 调 `task.cancel()`，wrapper 捕获 `CancelledError` 后 shield 写入 `cancelled` 终态。 |
| 启动 reconcile | `reconcile_on_boot()`（API startup 调用）把崩溃残留的 `starting/running` 行判 `failed(interrupted)`，避免 `/api/init-status` 永远报 running。 |
| bootstrap 归属 | `register_enqueued_task` / `is_owned_bootstrap_task` 给写者门控判断某 task-result 是否属于本 init run。 |

前置探测 `InitPrereqs`（`runtime/init_prereqs.py`）：`chat_ready()`（provider health，TTL 30s，超时乐观）、`bilibili_check()`（`validate_cookie`，ok 60s / fail 10s TTL）、`enabled_platforms()`；全部 TTL 缓存 + 单飞，避免轮询打爆。

## API 端点

| 端点 | 方法 | 访问 | 说明 |
|---|---|---|---|
| `/api/init-status` | GET | 远程可读 / 降级可读 | 权威进度 + 前置清单 + `can_start`（trusted-local && 硬前置 && 非 running && supported）/ `can_manage`（trusted-local）。远程不 403、`can_manage=false`。 |
| `/api/init` | POST | 仅本机 | 占坑前廉价拒绝（403 local_only / 409 unsupported_runtime / 409 already_initialized）→ `try_start`（409 already_running）→ 临界区复验前置（缺则复位 idle + 409，不留 stuck `starting` 行）→ 后台跑 wrapper → 202 + 初始 status。 |
| `/api/init/cancel` | POST | 仅本机 | 协作取消在跑的 run；无运行中 → 409 not_running。 |

`_init_wrapper`（`api/app.py`）是某次 API run 的**唯一**状态 / 事件写者：`mark_running` → `run_guided_init(coordinator=...)` → `complete(partial_success=...)`；`CancelledError` → shield `cancel`，`GuidedInitError` → `fail(reason)`，其它异常 → `fail("internal_error")`。三个 path 都在 `auth.py` 公共集 + 降级白名单。

## init 期间写者门控

防止并发写污染在跑的 init（`init_active()` 为真时）：

- **后台循环**：`background_llm_work_allowed()` 返回 False，一处暂停所有 daemon 后台 LLM 循环（account_sync / 连续 refresh / soul pipeline tick）。init 自身不受影响——它直调 `soul_engine` / `run_init_backfill`，二者都不查该 gate。
- **HTTP 写端**：`_init_active_write_guard` 中间件对 `/api/events`、`/api/feedback`、`/api/profile/edit`、`PUT /api/config`、`/api/recommendations/refresh`、兴趣 / 避雷探针触发、source 配方 CRUD 返回 `409 init_running`。
- **例外**：`/api/bilibili/cookie` 在 init 期间静默 no-op（不 validate、不 rebuild，避免热重载换掉正在用的客户端）；`/api/sources/*/task-result` **放行**（init 自己的 bootstrap 采集器要读它）。
- **热重载豁免**：`rebuild_from_config` 的 `cancel_all(exclude={"guided_init"})` 让 init 任务不被配置热重载取消。

## 插件 UI（extension）

推荐 tab 未初始化空状态渲染前置清单 + 「开始初始化」按钮 + 进度条，详见 [extension 模块文档](extension.md)。DOM 无关逻辑在 `extension/popup/popup-init-control.js`，单测在 `extension/tests/init-control.test.ts`。

## 测试

- `tests/test_init_coordinator.py` — 协调器生命周期 / 单飞 / 并行 stage / reconcile / 取消 / 接线 / `/api/init-status` 形状 / 门控后台暂停。
- `tests/test_init_prereqs.py` — 前置探测 TTL / 乐观超时。
- `tests/test_database.py` — `init_runs` CAS / 白名单列 / reconcile。
- `tests/test_api_app.py::TestGuidedInitEndpoints` — `/api/init`、`/api/init/cancel` 守门（403 / 409 各路径、复位不留 stuck 行）+ 写者门控（events 409 / cookie no-op / task-result 放行）。
- `tests/test_cli.py` — `openbiliclaw init` 全回归（共享流水线零回归）。
- `extension/tests/init-control.test.ts` — 清单 / 按钮态 / 进度状态机纯函数。
- 完整真号 GUI init（插件推荐 tab → 前置清单 → 开始 → 进度 → 画像 → 推荐）列入用户手测 DoD。
