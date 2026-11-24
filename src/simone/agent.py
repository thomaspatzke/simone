"""Pydantic AI agent for Sigma detection rule creation.

The Sigma functionality (validation, SigmaHQ search, logsource knowledge,
file names) comes from the Sigma MCP server, see :mod:`simone.sigma_mcp`.
The workflow instructions come from its ``create_sigma_rules`` prompt.
simone adds the tools that only make sense in its web chat: reading URLs and
uploaded PDFs, and saving rules to the configured output directory.
"""
from __future__ import annotations

import base64
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model

from simone.config import get_output_directory
from simone.sigma_mcp import create_toolset
from simone.tools.fetch_source import extract_pdf_bytes, fetch_source
from simone.tools.sigma_output import save_rule as save_rule_to_file

SIMONE_INSTRUCTIONS = """
## Working in simone

You run in simone's web chat. In addition to the Sigma MCP server tools you
have these tools:
- `fetch_url` reads a web page or PDF from a URL. Use it whenever the user
  gives a URL.
- `process_uploaded_pdf` extracts the text of a PDF the user attached. Pass
  its base64 content.
- `save_rule` saves a rule into simone's output directory. Call
  `suggest_rule_filename` first and pass the file name it returns. Existing
  files are never overwritten; a number is appended instead.
You may also use your built-in web search for additional threat context.
"""


def build_instructions(workflow: str) -> str:
    """Combine the server's workflow text with simone's own instructions."""
    return workflow.rstrip() + "\n" + SIMONE_INSTRUCTIONS


def create_agent(config: dict[str, Any], workflow: str) -> Agent:  # type: ignore[type-arg]
    """Create the agent with the Sigma MCP server tools and simone's own tools.

    Args:
        config: simone's configuration.
        workflow: The workflow text from the server (see
            :func:`simone.sigma_mcp.load_workflow`).
    """
    model_name: str = config.get("model", "openai:gpt-4o")
    agent: Agent = Agent(  # type: ignore[type-arg]
        _build_model(model_name),
        instructions=build_instructions(workflow),
        capabilities=_build_capabilities(model_name),
        toolsets=[create_toolset(config)],
    )
    register_tools(agent, config)
    return agent


def _build_model(model_name: str) -> Model | str:  # type: ignore[type-arg]
    """Build a model instance.

    For Anthropic models, creates an AnthropicModel directly so we can
    override the profile.  pydantic-ai 2.54 does not know that claude-haiku-5-5
    binds thinking blocks to the conversation prefix; without the flag the
    automatic drop-and-retry on stale-block 400 errors never fires.
    """
    if not model_name.startswith("anthropic:"):
        return model_name
    try:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.profiles.anthropic import AnthropicModelProfile

        raw_name = model_name.removeprefix("anthropic:")
        # Haiku 5.x binds thinking blocks like fable-5-1/opus-5-5/sonnet-5-5
        # but isn't in pydantic-ai's known list yet.  Setting the flag here
        # lets the built-in retry-with-drop_block mechanism handle the 400.
        profile: AnthropicModelProfile | None = None
        if raw_name.startswith("claude-haiku-5"):
            profile = AnthropicModelProfile(anthropic_binds_thinking_blocks=True)
        return AnthropicModel(raw_name, profile=profile)
    except ImportError:
        return model_name


def _build_capabilities(model_name: str) -> list:  # type: ignore[type-arg]
    caps = []
    try:
        from pydantic_ai.capabilities import WebSearch  # type: ignore[import-untyped]
        caps.append(WebSearch())
    except (ImportError, Exception):  # noqa: BLE001
        pass
    return caps


def register_tools(agent: Agent, config: dict[str, Any]) -> None:  # type: ignore[type-arg]
    """Register simone's local tools on the agent."""

    @agent.tool_plain
    async def fetch_url(url: str) -> str:
        """Fetch text content from a URL (web page or PDF). Returns the extracted text."""
        return await fetch_source(url)

    @agent.tool_plain
    def process_uploaded_pdf(content_base64: str) -> str:
        """Extract text from a base64-encoded PDF that was uploaded by the user.

        Pass the raw base64 string of the PDF file content.
        """
        try:
            data = base64.b64decode(content_base64)
        except Exception as exc:  # noqa: BLE001
            return f"[Error] Could not decode base64 PDF data: {exc}"
        return extract_pdf_bytes(data)

    @agent.tool_plain
    def save_rule(filename: str, rule_yaml: str) -> str:
        """Save a validated Sigma rule to simone's output directory.

        Get the file name from the `suggest_rule_filename` tool first. If the
        file exists, a number is appended (e.g. name_2.yml) instead of
        overwriting it.

        Args:
            filename: File name from `suggest_rule_filename`, e.g.
                `proc_creation_win_psexec_remote_execution.yml`.
            rule_yaml: The complete, validated YAML of the rule.

        Returns:
            A confirmation with the path the rule was saved to, or an error.
        """
        try:
            return save_rule_to_file(rule_yaml, filename, get_output_directory(config))
        except ValueError as exc:
            return f"[Error] Could not save rule: {exc}"
        except OSError as exc:
            return f"[Error] Could not write the rule file: {exc}"
