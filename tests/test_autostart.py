"""Tests for boot autostart runtime helpers."""

import sys
from pathlib import Path

import pytest

from openbiliclaw.config import Config, save_config


def test_active_env_managed_inputs_detects_known_external_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openbiliclaw.runtime.autostart.guards import active_env_managed_inputs

    cfg = Config()
    cfg.sources.douyin.cookie_env = "CUSTOM_DOUYIN_COOKIE"
    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", "/tmp/openbiliclaw")
    monkeypatch.setenv("OPENBILICLAW_LLM_DEFAULT_PROVIDER", "ollama")
    monkeypatch.setenv("OPENBILICLAW_API_AUTH_PASSWORD", "secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "gemini-key")
    monkeypatch.setenv("CUSTOM_DOUYIN_COOKIE", "sid=1")

    assert active_env_managed_inputs(cfg) == [
        "CUSTOM_DOUYIN_COOKIE",
        "GOOGLE_API_KEY",
        "OPENBILICLAW_API_AUTH_PASSWORD",
        "OPENBILICLAW_LLM_DEFAULT_PROVIDER",
    ]


def test_active_env_managed_inputs_ignores_empty_or_project_root_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openbiliclaw.runtime.autostart.guards import active_env_managed_inputs

    cfg = Config()
    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", "/tmp/openbiliclaw")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    assert active_env_managed_inputs(cfg) == []


def test_autostart_shadowed_detects_config_local_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openbiliclaw.runtime.autostart.guards import autostart_shadowed

    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", str(tmp_path))
    cfg = Config()
    cfg.autostart.enabled = False
    save_config(cfg, autostart_authoritative=True)
    (tmp_path / "config.local.toml").write_text(
        "[autostart]\nenabled = true\n",
        encoding="utf-8",
    )

    assert autostart_shadowed(False) is True


def test_autostart_shadowed_false_when_effective_matches_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openbiliclaw.runtime.autostart.guards import autostart_shadowed

    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", str(tmp_path))
    cfg = Config()
    cfg.autostart.enabled = True
    save_config(cfg, autostart_authoritative=True)

    assert autostart_shadowed(True) is False


def test_build_launch_spec_uses_python_module_and_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openbiliclaw.runtime.autostart.command import build_launch_spec

    ollama_bin = tmp_path / "bin" / "ollama"
    ollama_bin.parent.mkdir()
    ollama_bin.write_text("", encoding="utf-8")
    monkeypatch.setenv("OPENBILICLAW_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda name: str(ollama_bin) if name == "ollama" else None)

    spec = build_launch_spec(Config())

    assert spec.argv == [sys.executable, "-m", "openbiliclaw.cli", "start"]
    assert spec.working_dir == tmp_path
    assert spec.env["OPENBILICLAW_PROJECT_ROOT"] == str(tmp_path)
    assert str(ollama_bin.parent) in spec.env["PATH"].split(":")


def test_resolve_pythonw_falls_back_when_missing(tmp_path: Path) -> None:
    from openbiliclaw.runtime.autostart.command import resolve_pythonw

    python_exe = tmp_path / "python.exe"
    python_exe.write_text("", encoding="utf-8")

    assert resolve_pythonw(python_exe) == python_exe


def test_unsupported_autostart_status_has_none_mechanism(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openbiliclaw.runtime import autostart

    monkeypatch.setattr(autostart.sys, "platform", "aix")
    monkeypatch.setattr(autostart.docker_runtime, "is_running_in_container", lambda: False)

    status = autostart.status()

    assert status.supported is False
    assert status.registered is False
    assert status.platform == "aix"
    assert status.mechanism == "none"
    assert status.reason == "unsupported_platform"


def test_docker_autostart_status_is_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from openbiliclaw.runtime import autostart

    monkeypatch.setattr(autostart.docker_runtime, "is_running_in_container", lambda: True)

    status = autostart.status()

    assert status.supported is False
    assert status.mechanism == "none"
    assert status.reason == "unsupported_docker_runtime"
