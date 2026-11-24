"""Connection to the Sigma MCP server, which provides all Sigma functionality.

simone starts ``sigma-mcp-server`` as a stdio subprocess.  The server
validates rules, searches the SigmaHQ repository, knows the logsources and
suggests file names; it also provides the ``create_sigma_rules`` workflow
that simone uses as its system prompt.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from fastmcp.client.transports import StdioTransport
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import TextContent

WORKFLOW_PROMPT = "create_sigma_rules"
"""Name of the server prompt that holds the rule-creation workflow."""

# The MCP SDK starts stdio servers with a minimal environment (on POSIX only
# HOME, LOGNAME, PATH, SHELL, TERM and USER).  The server needs a few more
# variables to download the SigmaHQ rules and MITRE data, e.g. behind a
# proxy.  Only these are passed on, so simone's API keys stay in simone.
_FORWARDED_ENV = re.compile(
    r"^(HTTPS?_PROXY|ALL_PROXY|NO_PROXY|SSL_CERT_FILE|SSL_CERT_DIR"
    r"|REQUESTS_CA_BUNDLE|CURL_CA_BUNDLE|XDG_CACHE_HOME|SIGMA_MCP_\w+)$",
    re.IGNORECASE,
)


def default_command() -> str:
    """Return the ``sigma-mcp-server`` installed next to simone, if any.

    Prefers the executable in the same environment as the running Python, so
    simone uses the server version it was installed with.
    """
    scripts = Path(sys.executable).parent
    for name in ("sigma-mcp-server", "sigma-mcp-server.exe"):
        candidate = scripts / name
        if candidate.is_file():
            return str(candidate)
    return shutil.which("sigma-mcp-server") or "sigma-mcp-server"


def server_environment(configured: dict[str, Any] | None = None) -> dict[str, str]:
    """Environment variables for the server process.

    Proxy, CA and ``SIGMA_MCP_*`` variables are taken from simone's
    environment; values from the ``sigma_mcp.env`` config section override
    them.
    """
    env = {key: value for key, value in os.environ.items() if _FORWARDED_ENV.match(key)}
    env.update({str(k): str(v) for k, v in (configured or {}).items()})
    return env


def create_transport(config: dict[str, Any], *, warmup: bool = True) -> StdioTransport:
    """Build the stdio transport that starts the server.

    Args:
        config: simone's configuration (see :mod:`simone.config`).
        warmup: Whether the server builds its rule index and loads MITRE data
            in the background.  Disabled for short-lived helper connections.
    """
    settings = config.get("sigma_mcp", {}) or {}
    env = server_environment(settings.get("env"))
    if not warmup:
        env["SIGMA_MCP_NO_WARMUP"] = "1"
    return StdioTransport(
        command=settings.get("command") or default_command(),
        args=[str(arg) for arg in settings.get("args") or []],
        env=env,
        keep_alive=warmup,
    )


def create_toolset(config: dict[str, Any]) -> MCPToolset[Any]:
    """Toolset exposing all server tools to the agent.

    The server process stays alive between agent runs (``keep_alive``), so
    its rule index and caches survive across chat messages.
    """
    return MCPToolset(create_transport(config), id="sigma")


async def load_workflow(config: dict[str, Any]) -> str:
    """Fetch the rule-creation workflow text from the server.

    Raises:
        RuntimeError: The server did not return a text prompt.
    """
    toolset: MCPToolset[Any] = MCPToolset(create_transport(config, warmup=False))
    async with toolset:
        result = await toolset.get_prompt(WORKFLOW_PROMPT)
    texts = [m.content.content for m in result.messages if isinstance(m.content, TextContent)]
    if not texts:
        raise RuntimeError(f"The Sigma MCP server returned no text for {WORKFLOW_PROMPT!r}.")
    return "\n\n".join(texts)
