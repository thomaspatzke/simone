# SIMONE - Sigma Modeling Engine

**SIMONE** (Sigma Modeling Engine) is an AI-powered tool for generating and validating Sigma detection rules.

## Overview

This project leverages AI agents to help security teams create, refine, and validate Sigma detection rules—a standardized format for describing security event patterns. SIMONE streamlines the process of developing robust threat detection rules by automating rule generation, validation, and correlation analysis.

## Key Features

- **Rule Generation**: AI-assisted creation of Sigma detection rules
- **Rule Validation**: Automated validation of rule syntax and logic
- **Correlation Analysis**: Support for correlating multiple detection rules
- **Source Integration**: Tools to fetch and integrate various log sources
- **Repository Management**: Integration with Sigma rule repositories

## Project Structure

- `src/simone/` - Core AI agent implementation
- `tests/` - Test suite
- `output/` - Generated Sigma detection rules
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

The agent will:
- Download the Sigma rule repository (if not already present)
- Build the search index
- Start the web server at `http://127.0.0.1:7932`

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

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
