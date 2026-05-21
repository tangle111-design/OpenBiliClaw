# 内联惊喜推荐聊天 Spec

## 背景

当前移动端和插件的惊喜推荐"聊一聊"按钮直接跳转到对话 tab，丢失了上下文——用户不知道在聊哪条内容，AI 也容易混淆。应该像推荐卡片的"说说原因"一样，在惊喜推荐卡片内展开内联聊天。

## 目标

惊喜推荐的"聊一聊"按钮点击后，在卡片内部展开一个聊天 composer + 回复区域，而不是切换到对话 tab。用户可以原地和 AI 讨论这条推荐内容。

## 范围

### 移动端 Web (`src/openbiliclaw/web/`)

1. **recommend.js — renderDelightTray()**
   - "聊一聊"按钮点击后，在 delight tray 内部展开一个 composer 区域（textarea + 发送按钮）
   - 展开后 composer 获得焦点，placeholder 显示"聊聊这条推荐…"
   - 发送消息后调用 `POST /api/chat` with scope=delight, subject_id=bvid, subject_title=title
   - 在 composer 上方显示对话气泡（用户消息 + AI 回复）
   - 支持多轮对话，不限制轮数
   - 关闭 composer 不清空历史，重新展开可以继续聊

2. **app.css**
   - 新增 `.delight-composer`、`.delight-chat-bubble` 等样式
   - composer 展开/收起动画

3. **状态管理**
   - 每个 delight 的聊天状态（turns、composer_open、draft）存在 delight 对象上
   - `rerenderDelightOnly()` 可以局部更新，不影响推荐列表

### 插件 Popup (`extension/popup/`)

4. **popup.js — renderDelightSlot()**
   - 对齐移动端行为：点"聊一聊"在 banner body 内展开 composer
   - 当前插件已有部分 delight chat 逻辑（`expandDelightChat`、`composer_open` 状态），需要确认是否已实现并修复

### 后端

5. **无需改动** — 已有 `POST /api/chat` 支持 scope=delight + subject_id/subject_title

## 对齐插件已有行为

插件 popup 已经有 delight 内联聊天的部分实现：
- `delight.composer_open` 状态
- `chat_draft` 和 `chat_reply` 字段
- `expandDelightChat()` 函数

移动端应该对齐这个行为模式，而不是重新设计。

## 验收标准

- [ ] 移动端惊喜推荐"聊一聊"不再跳转对话 tab
- [ ] 点击后在卡片内展开 textarea + 发送按钮
- [ ] 发送消息后显示用户气泡 + AI 回复气泡
- [ ] 支持多轮对话
- [ ] 左右箭头切换惊喜推荐时保留各自的聊天历史
- [ ] 插件 popup 的惊喜推荐聊天行为与移动端一致
- [ ] composer 展开时 font-size >= 16px（防止 iOS Safari 缩放）
- [ ] 局部更新，不触发全页面白屏刷新
