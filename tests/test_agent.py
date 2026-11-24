"""End-to-end tests of the agent with the real Sigma MCP server.

A scripted FunctionModel replaces the LLM, so no API key or network access is
needed: the server runs without warm-up, so it does not download anything.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from simone.agent import SIMONE_INSTRUCTIONS, build_instructions, create_agent

RULE = """title: Suspicious Whoami Execution
id: 0b5b3d5c-1a8e-4d4c-9f29-3c6c8e0b7a01
status: experimental
description: Detects whoami.
author: Test
date: 2026-11-24
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\\whoami.exe'
    condition: selection
level: low
"""


def _config(tmp_path: Path) -> dict[str, Any]:
    return {
        "model": "test",
        "output": {"directory": str(tmp_path / "rules")},
        "sigma_mcp": {
            "env": {"SIGMA_MCP_DATA_DIR": str(tmp_path / "data"), "SIGMA_MCP_NO_WARMUP": "1"}
        },
    }


def _returns(messages: list[ModelMessage]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for message in messages:
        for part in getattr(message, "parts", []):
            if isinstance(part, ToolReturnPart):
                found[part.tool_name] = part.content
    return found


def test_build_instructions() -> None:
    text = build_instructions("Workflow text\n\n")
    assert text.startswith("Workflow text\n")
    assert text.endswith(SIMONE_INSTRUCTIONS)


def test_agent_uses_server_and_local_tools(tmp_path: Path) -> None:
    seen_tools: list[str] = []

    def script(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen_tools[:] = [tool.name for tool in info.function_tools]
        done = _returns(messages)
        if "suggest_rule_filename" not in done:
            return ModelResponse(
                parts=[
                    ToolCallPart("validate_rule", {"rule_yaml": RULE}),
                    ToolCallPart("suggest_rule_filename", {"rule_yaml": RULE}),
                ]
            )
        if "save_rule" not in done:
            suggestion = done["suggest_rule_filename"]
            if isinstance(suggestion, str):
                suggestion = json.loads(suggestion)
            return ModelResponse(
                parts=[ToolCallPart("save_rule", {"filename": suggestion["filename"], "rule_yaml": RULE})]
            )
        return ModelResponse(parts=[TextPart("saved")])

    config = _config(tmp_path)
    agent = create_agent(config, "Workflow")
    agent.model = FunctionModel(script)

    async def run_twice() -> tuple[Any, Any]:
        first = await agent.run("Create a rule for whoami")
        second = await agent.run("Create it again")
        return first, second

    first, second = asyncio.run(run_twice())

    # Tools from the Sigma MCP server and simone's own tools are both offered.
    assert {"validate_rule", "search_rules", "suggest_rule_filename", "read_resource"} <= set(seen_tools)
    assert {"fetch_url", "process_uploaded_pdf", "save_rule"} <= set(seen_tools)
    assert first.output == second.output == "saved"

    saved = sorted(p.name for p in (tmp_path / "rules").iterdir())
    assert saved == [
        "proc_creation_win_suspicious_whoami_execution.yml",
        "proc_creation_win_suspicious_whoami_execution_2.yml",
    ]
    assert (tmp_path / "rules" / saved[0]).read_text(encoding="utf-8") == RULE
