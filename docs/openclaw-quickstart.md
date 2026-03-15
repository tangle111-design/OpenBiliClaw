# OpenClaw 接入最短指南

> 给 OpenClaw 和维护者的最短落地说明：怎么安装 OpenBiliClaw、怎么初始化、怎么确认 adapter 已可调用。

## 适用场景

当你希望 OpenClaw 在当前仓库里直接调用 OpenBiliClaw 的学习与推荐能力时，使用这份指南。

当前接入方式不是 Python SDK 注册，而是：

1. 仓库根目录提供 workspace skill：`skills/openbiliclaw-adapter/SKILL.md`
2. skill 通过 JSON CLI bridge 调用：`src/openbiliclaw/integrations/openclaw/cli.py`
3. CLI bridge 再调用内部 adapter operation

## 前置条件

- 已克隆当前仓库
- 本机可用 Python 3.11+
- 可以访问当前配置所需的 LLM provider
- 准备好 B 站 Cookie，或能在交互式终端里现场输入

## 安装项目

在仓库根目录执行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.toml config.toml
```

然后至少确认两件事：

1. `config.toml` 里有可用的 LLM provider 配置
2. 有可用的 B 站登录态

如果你不想手动编辑完整配置，也可以直接进入初始化命令，让它在交互式终端中引导你补齐缺项。

## 首次初始化

首次运行必须先做一次初始化：

```bash
openbiliclaw init
```

初始化会顺序完成这些步骤：

1. 检查 LLM 配置
2. 检查 B 站认证
3. 拉取历史
4. 写入事件并分析偏好
5. 生成初始画像
6. 自动补首轮内容池

如果当前终端是交互式，且缺少 API Key 或 B 站 Cookie，`openbiliclaw init` 会直接提示你输入。

如果是 Docker 部署，推荐入口是：

```bash
docker exec -it openbiliclaw-backend openbiliclaw init
```

## OpenClaw 侧最小接线

OpenClaw 当前应直接发现仓库里的 workspace skill：

- `skills/openbiliclaw-adapter/SKILL.md`

这个 skill 不直接实现推荐逻辑，而是要求 OpenClaw 调下面的 CLI bridge：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli <command> [flags]
```

已支持的命令：

- `sync-account`
- `get-profile`
- `runtime-status`
- `recommend --limit 5`
- `recommend --limit 5 --refresh-if-needed`
- `submit-feedback --recommendation-id 7 --feedback-type like`
- `doctor`
- `emit-skill-descriptors`

## 初始化后自检

建议按下面顺序做一次最短冒烟：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli doctor
uv run python -m openbiliclaw.integrations.openclaw.cli get-profile
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

期望结果：

1. `doctor` 返回 `skill_pack_exists: true`
2. `get-profile` 返回 `{"ok": true, "data": ...}`
3. `recommend --limit 3` 返回推荐列表

如果你明确要触发较重的 refresh 路径，再执行：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3 --refresh-if-needed
```

默认不建议把这个重路径作为 OpenClaw 的常规入口。

## OpenClaw 调用约定

给 OpenClaw 的规则建议保持为：

1. 优先用 `recommend --limit <n>`，这是快路径
2. 只有明确需要新鲜度检查时，才加 `--refresh-if-needed`
3. 解析 CLI 返回 JSON，不要依赖自然语言输出
4. 如果返回 `{ "ok": false, ... }`，直接上抛错误，不要继续串后续动作
5. 对 `comment` 反馈，必须带 `--note`

## 常见问题

### 1. `doctor` 失败

优先检查：

- 当前目录是不是仓库根目录
- 虚拟环境是否已激活
- 依赖是否已安装
- `src/openbiliclaw/integrations/openclaw/cli.py` 是否存在
- `skills/openbiliclaw-adapter/SKILL.md` 是否存在

### 2. `get-profile` 或 `recommend` 报未初始化

说明还没有完成：

```bash
openbiliclaw init
```

### 3. 显式 refresh 太慢

这是预期风险之一。OpenClaw 交互默认应走快路径：

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

只有在用户明确要求更强新鲜度时，才触发 `--refresh-if-needed`。
