# SIMONE - Sigma Modeling Engine

**SIMONE** (Sigma Modeling Engine) is an AI-powered tool for generating and validating Sigma detection rules.

## Overview

This project leverages AI agents to help security teams create, refine, and validate Sigma detection rules—a standardized format for describing security event patterns. SIMONE streamlines the process of developing robust threat detection rules by automating rule generation, validation, and correlation analysis.

## Architecture

simone is a web chat front end for the
[Sigma MCP server](https://github.com/SigmaHQ/sigma-mcp-server)
([PyPI](https://pypi.org/project/sigma-mcp-server/)), which it starts as a
subprocess. The server provides all Sigma functionality: rule validation with
pySigma, search in the SigmaHQ rule repository, logsource knowledge,
SigmaHQ-style file names and the rule-creation workflow that simone uses as
its system prompt. simone adds reading URLs and uploaded PDFs and saving rules
to a local directory.

The same workflow is available in other MCP clients, for example in Claude
Code as `/mcp__sigma__create_sigma_rules` after
`claude mcp add sigma -- uvx sigma-mcp-server`.

## Key Features

- **Rule Generation**: AI-assisted creation of Sigma detection rules
- **Rule Validation**: Automated validation of rule syntax and logic
- **Correlation Analysis**: Support for correlating multiple detection rules
- **Source Integration**: Tools to fetch and integrate various log sources
- **Repository Management**: Integration with Sigma rule repositories

## Project Structure

- `src/simone/agent.py` - Agent: workflow from the server plus simone's own tools
- `src/simone/sigma_mcp.py` - Connection to the Sigma MCP server
- `src/simone/tools/` - Reading URLs and PDFs, saving rules
- `tests/` - Test suite
- `config.yaml` - Configuration file for the application

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd simone
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```
   Or with pip:
   ```bash
   pip install -e .
   ```

### Configuration

1. Copy the example configuration:
   ```bash
   cp config.yaml.example config.yaml
   ```

2. Edit `config.yaml` and configure your AI model provider and API keys:
   - Set the `model` parameter (e.g., `anthropic:claude-3-5-sonnet-20241022`)
   - Add your API key(s) under `api_keys` for your chosen provider

### Running the Agent

Start the AI agent web server:

```bash
uv run simone
```

Or with pip:
```bash
simone
```

simone starts the Sigma MCP server and the web server at
`http://127.0.0.1:7932`. On first use the Sigma MCP server downloads the
SigmaHQ rule repository in the background and builds its search index; this
takes a moment, and rule search becomes available once it has finished.

The `sigma_mcp` section of `config.yaml` selects the server command and
passes extra environment variables to it, for example `SIGMA_MCP_DATA_DIR` to
choose where the rules are cached. Proxy and CA settings (`HTTPS_PROXY`,
`SSL_CERT_FILE`, ...) and `SIGMA_MCP_*` variables are passed on
automatically.

### Opening the Web UI

Once the server is running, open your web browser and navigate to:

```
http://127.0.0.1:7932
```

You can now interact with the SIMONE agent to:
- Generate new Sigma detection rules
- Validate existing rules
- Analyze correlations between rules
- Search the Sigma rule repository

## Development

```bash
uv sync
uv run pytest
```

The tests start the real Sigma MCP server without network access and use a
scripted model, so they need no API key.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
