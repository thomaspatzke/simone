"""Tests for configuration loading."""
from __future__ import annotations

from pathlib import Path

import pytest

from simone.config import load_config


def test_defaults_without_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = load_config(str(tmp_path / "missing.yaml"))
    assert config["sigma_mcp"] == {"command": "", "args": [], "env": {}}
    assert "No config.yaml found" in capsys.readouterr().out


def test_sigma_mcp_section_is_merged(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("sigma_mcp:\n  env:\n    SIGMA_MCP_DATA_DIR: /data\n", encoding="utf-8")
    config = load_config(str(path))
    assert config["sigma_mcp"]["env"] == {"SIGMA_MCP_DATA_DIR": "/data"}
    assert config["sigma_mcp"]["command"] == ""


def test_obsolete_sigma_repo_section_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("sigma_repo:\n  path: ~/.simone/sigma-rules\n", encoding="utf-8")
    load_config(str(path))
    assert "'sigma_repo' section is no longer used" in capsys.readouterr().out
