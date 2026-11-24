"""Tests for the connection to the Sigma MCP server."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from simone import sigma_mcp
from simone.sigma_mcp import (
    WORKFLOW_PROMPT,
    create_toolset,
    create_transport,
    default_command,
    load_workflow,
    server_environment,
)


class TestServerEnvironment:
    def test_forwards_only_network_and_server_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
        monkeypatch.setenv("no_proxy", "localhost")
        monkeypatch.setenv("SSL_CERT_FILE", "/etc/ca.pem")
        monkeypatch.setenv("SIGMA_MCP_DATA_DIR", "/data")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
        monkeypatch.setenv("PYSIGMA_ALLOW_VARS_EXECUTION", "1")
        env = server_environment()
        assert env["HTTPS_PROXY"] == "http://proxy:3128"
        assert env["no_proxy"] == "localhost"
        assert env["SSL_CERT_FILE"] == "/etc/ca.pem"
        assert env["SIGMA_MCP_DATA_DIR"] == "/data"
        assert "ANTHROPIC_API_KEY" not in env
        assert "PYSIGMA_ALLOW_VARS_EXECUTION" not in env

    def test_configured_values_win(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIGMA_MCP_DATA_DIR", "/from-env")
        env = server_environment({"SIGMA_MCP_DATA_DIR": "/from-config", "OTHER": 7})
        assert env["SIGMA_MCP_DATA_DIR"] == "/from-config"
        assert env["OTHER"] == "7"


class TestTransport:
    def test_defaults(self) -> None:
        transport = create_transport({})
        assert transport.command == default_command()
        assert transport.args == []
        assert transport.keep_alive is True
        assert "SIGMA_MCP_NO_WARMUP" not in (transport.env or {})

    def test_configured(self) -> None:
        config = {"sigma_mcp": {"command": "/opt/sigma-mcp", "args": ["--x", 1], "env": {"A": "b"}}}
        transport = create_transport(config)
        assert transport.command == "/opt/sigma-mcp"
        assert transport.args == ["--x", "1"]
        assert (transport.env or {})["A"] == "b"

    def test_helper_connection_skips_warmup(self) -> None:
        transport = create_transport({}, warmup=False)
        assert (transport.env or {})["SIGMA_MCP_NO_WARMUP"] == "1"
        assert transport.keep_alive is False

    def test_toolset_uses_transport(self) -> None:
        toolset = create_toolset({})
        assert toolset.id == "sigma"


class TestDefaultCommand:
    def test_prefers_server_next_to_python(self) -> None:
        installed = Path(sys.executable).parent / "sigma-mcp-server"
        assert installed.is_file(), "sigma-mcp-server must be installed with simone"
        assert default_command() == str(installed)

    def test_falls_back_to_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sigma_mcp.sys, "executable", str(tmp_path / "python"))
        monkeypatch.setattr(sigma_mcp.shutil, "which", lambda name: None)
        assert default_command() == "sigma-mcp-server"


def _offline_config(tmp_path: Path) -> dict[str, object]:
    return {
        "sigma_mcp": {
            "env": {"SIGMA_MCP_DATA_DIR": str(tmp_path / "data"), "SIGMA_MCP_NO_WARMUP": "1"}
        }
    }


class TestLoadWorkflow:
    def test_from_real_server(self, tmp_path: Path) -> None:
        workflow = asyncio.run(load_workflow(_offline_config(tmp_path)))
        assert "Sigma detection engineer" in workflow
        assert "suggest_rule_filename" in workflow
        assert WORKFLOW_PROMPT == "create_sigma_rules"

    def test_unstartable_server(self, tmp_path: Path) -> None:
        config = {"sigma_mcp": {"command": str(tmp_path / "missing-server")}}
        with pytest.raises(Exception):
            asyncio.run(load_workflow(config))
