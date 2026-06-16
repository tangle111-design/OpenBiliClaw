# 技术债清单

> 本文档只记录已经确认会影响长期可靠性、成本或可维护性的技术债。
> 普通 TODO、历史计划里的占位项和已经修复的债务不直接进入“当前已确认技术债”，
> 但会在“待确认线索”里保留索引，方便后续判断是否需要升级。

更新时间：2026-06-16

---

## 当前已确认技术债

### TD-001：串行化画像写入

**状态**：Open

**影响范围**：`preference.json`、`soul.json`、`cognition_updates.json`

**问题**

多条画像更新路径可能并发读旧状态，然后整体覆盖写回：

- `SoulEngine.learn_from_dialogue()`
- `SoulEngine.process_feedback_batch_if_needed()`
- `ProfileUpdatePipeline`
- profile consolidation
- dislike writeback

这些路径目前缺少统一的 profile mutation queue / lock，也没有在提交前基于最新
`preference.json` / `soul.json` 做 rebase / merge。高并发或后台任务重叠时可能出现
last-write-wins，丢失刚新增的兴趣、避雷方向或 cognition update。

**风险**

- 用户刚反馈的避雷方向被另一条后台画像写入覆盖。
- 聊天学习刚新增的兴趣被反馈批处理覆盖。
- UI 展示的“阿B 最近新记住了什么”和实际画像状态不一致。

**建议方向**

- 引入统一 profile mutation queue，所有写 `preference/soul/cognition` 的路径串行执行。
- 或者为每次写入增加提交前 rebase：重新读取最新文件，将本次变更 merge 后再保存。
- 为并发路径补端到端回归测试，覆盖 dialogue learning 与 feedback batch 同时写入。

---

### TD-002：限制 Soul 重建时 awareness / insight 输入体积

**状态**：Open

**影响范围**：`ProfileBuilder.build()`、`build_soul_profile_prompt()`、`awareness.json`、`insight.json`

**问题**

当前 `ProfileBuilder.build()` 会把 `_load_awareness_notes()` 和 `_load_insights()`
的全量 JSON 传入 `build_soul_profile_prompt()`。认知周期同步到 `soul.json` 快照时只保留：

- 最近 8 条 awareness
- 最近 6 条 insight

但画像重建 prompt 没有复用该窗口，也没有 prompt-size guard。随着
`awareness.json` / `insight.json` 长期增长，Soul 重建上下文可能越来越长。

**风险**

- Profile build prompt 超过模型上下文，导致画像重建失败。
- 大量旧 awareness / insight 稀释最新有效信号，让画像重建不够贴近当前状态。
- 重建成本随时间线性上涨。

**建议方向**

- 重建 Soul 时对 awareness / insight 做确定性裁剪，例如：
  - 最近窗口优先；
  - validated / high-confidence insight 优先；
  - 保留少量长期高价值洞察。
- 对旧 awareness / insight 先生成 compact cognition summary，再作为长期摘要输入。
- 增加 prompt-size guard；超过预算时先压缩 cognition 输入，而不是只 compact history。
- 增加回归测试，构造大量 awareness / insight，断言 profile build prompt 仍在预算内。

---

## 待确认线索

以下项目是仓库中仍能搜到的 TODO / debt 线索。它们不一定都是当前有效技术债，
后续需要先确认生产路径是否仍使用，再决定是否升级为正式 TD 编号。

### `src/openbiliclaw/agent/orchestrator.py`

该文件仍有一组初始化、发现、反馈、对话和关闭流程 TODO。看起来更像早期 agent
shell 的占位实现；当前主要运行时已迁移到 CLI / API / runtime controller /
SoulEngine 组合。需要确认该 orchestrator 是否仍有生产入口。若无生产入口，可考虑删除
或标注 deprecated；若仍是目标接口，则应拆成独立实施任务。

### `src/openbiliclaw/memory/manager.py`

`propagate_event()` 附近仍有“是否触发 preference / awareness / soul 层更新”的 TODO，
另有 `top_down_reinterpret()` 未实现。当前实际更新主要由 `SoulEngine`、
`ProfileUpdatePipeline` 和 `CognitionCycle` 驱动，因此这些 TODO 可能是旧架构遗留。
需要确认是否保留为未来顶层重解释能力，或删除以减少误导。

### `src/openbiliclaw/soul/dialogue.py`

`SocraticDialogue.extract_insights()` 仍是 TODO，但当前对话理解已经由
`DialogueInsightAnalyzer` 和 `SoulEngine.learn_from_dialogue()` 接管。该方法可能是旧接口遗留；
建议确认是否还有调用方，没有则删除或改成委托新 analyzer。

### `src/openbiliclaw/recommendation/engine.py`

仍有 “Use LLM to create a personal topic narrative” TODO。该项属于推荐文案 / 主题叙事增强，
不是当前画像可靠性问题。若产品上仍需要，可作为 recommendation 模块体验增强任务单独规划。

### `src/openbiliclaw/eval/agents.py`

评估说明里提到 `layer_updaters._update_role/values/core()` 当前可能仍是 TODO / no-op。
需要用当前代码确认这些 updater 在生产管线中的真实状态；如果仍未生效，可能会影响五层画像
从信号层向 Role / Values / Core 的增量更新能力。

---

## 已修复债务索引

- 觉察/洞察认知链生命周期治理：v0.3.125 已补齐洞察反馈软作废接线，并将 awareness / insight
  生成从固定窗口改为游标增量取数。详见 `docs/changelog.md` 的
  “觉察/洞察认知链补齐生命周期管理”条目。
