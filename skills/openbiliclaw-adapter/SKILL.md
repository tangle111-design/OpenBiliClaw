---
name: openbiliclaw_adapter
description: Use OpenBiliClaw's adapter CLI to sync account signals, read profile summaries, fetch recommendations, submit feedback, and inspect runtime status.
user-invocable: true
---

# OpenBiliClaw Adapter Skill

Use this skill when you are inside the OpenBiliClaw workspace and need current OpenBiliClaw state or want to push feedback back into the learning loop.

## Environment Bootstrap

If the workspace is not ready yet, bootstrap it before calling the adapter:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.toml config.toml
```

Then initialize OpenBiliClaw once:

```bash
openbiliclaw init
```

If `config.toml` is still missing API Key or B 站 Cookie and the terminal is interactive, `openbiliclaw init` will guide the operator through setup. After init, verify the adapter bridge:

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli doctor
```

For a longer setup guide, read `docs/openclaw-quickstart.md`.

## Command Bridge

Always call the adapter through the JSON CLI bridge:

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli <command> [flags]
```

Supported commands:

- `sync-account`
- `get-profile`
- `runtime-status`
- `recommend --limit 5`
- `recommend --limit 5 --refresh-if-needed`
- `submit-feedback --recommendation-id 7 --feedback-type like --note "很对胃口"`

## Working Rules

1. Parse the returned JSON instead of relying on prose.
2. If the JSON payload is `{ "ok": false, ... }`, surface the error and stop.
3. Prefer `recommend --limit <n>` for normal recommendation fetches. This is the fast path and does not trigger runtime refresh by default.
4. Use `--refresh-if-needed` only when the user explicitly wants a heavier freshness check before recommendation fetch.
5. For `comment` feedback, always include `--note`.

## Examples

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli get-profile
```

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3
```

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli recommend --limit 3 --refresh-if-needed
```

```bash
uv run python -m openbiliclaw.integrations.openclaw.cli submit-feedback \
  --recommendation-id 12 \
  --feedback-type comment \
  --note "方向对，但我想看更深一点。"
```
