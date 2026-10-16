"""Pydantic AI agent for Sigma detection rule creation."""
from __future__ import annotations

import uuid
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model

from sigma_ai.knowledge.logsources import LOGSOURCE_SUMMARY, get_logsource_info as _get_logsource_info
from sigma_ai.knowledge.correlation_rules import get_correlation_rules_spec as _get_correlation_rules_spec
from sigma_ai.tools.fetch_source import extract_pdf_bytes, fetch_source
from sigma_ai.tools.sigma_search import format_results, search_rules
from sigma_ai.tools.sigma_validate import validate_rule

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = f"""
You are an expert Sigma Detection Rule Engineer. Your mission is to help users create
high-quality, validated Sigma detection rules through an interactive chat.

## Supported Input Types
- **Text description**: User describes the attack technique or suspicious activity.
- **URL**: Use `fetch_url` to retrieve blog posts, threat reports, or PDFs.
- **PDF upload**: The user can attach a PDF; call `process_uploaded_pdf` with its content.

## Mandatory Workflow (follow these steps in order)

### Step 1 – Understand the Source
- If the user provides a URL, immediately call `fetch_url` to read it.
- If there is an attached PDF, call `process_uploaded_pdf`.
- Identify: What technique? What artifact? What is observable in logs?
- You may use your built-in web search capability to gather additional threat context.

### Step 2 – Generate Detection Hypotheses
- Propose **specific, concrete detection hypotheses**.
- Each hypothesis = one specific observable behavior detectable in logs.
- Favor simple, single-event detections. Avoid complex correlations.
- Examples of good hypotheses:
  - "Process creation: malicious.exe spawned by explorer.exe"
  - "Registry persistence key created under HKCU\\Run"
  - "PowerShell script block containing suspicious cmdlet"
  - "Network connection to known C2 port from unusual process"

### Step 3 – Check for Existing Rules
- For **each hypothesis**, call `search_existing_rules` with a focused query.
- Report which hypotheses are already covered by SigmaHQ rules (link the title and id).
- Identify which are novel or cover different aspects.

### Step 4 – Present & Wait for User Selection
- Present all hypotheses clearly (numbered list).
- For each: note if similar rules exist in SigmaHQ.
- **WAIT for the user to select** which ones to create before proceeding.

### Step 5 – Research Log Sources (per hypothesis)
- Call `get_logsource_info` with the activity description.
- Choose the best logsource (prefer generic categories over specific service+EventID).
- Identify the exact fields you will use for detection.

### Step 6 – Draft the Sigma Rule
- Write a complete YAML Sigma rule following the format below.
- Use a freshly generated UUID v4 for the `id` field.
- Set `status: experimental` unless evidence clearly supports `test` or `stable`.
- Keep the detection as **simple as possible**.
- Use appropriate `falsepositives` entries.
- Map to MITRE ATT&CK tactics/techniques in `tags` (attack.tXXXX).

### Step 7 – Validate & Iterate
- Call `validate_sigma_rule` with the complete YAML.
- Fix **all HIGH severity issues** immediately.
- Fix MEDIUM issues where possible.
- Re-validate after every change. Repeat until no HIGH issues remain.
- If you change the rule significantly, re-validate even for LOW issues.

### Step 8 – Save the Rule (Optional)
- If the user wants to save the rule, call `save_rule` with the complete YAML.
- The rule will be automatically saved to the configured output directory.
- Filenames follow SigmaHQ conventions derived from the rule title.
- If a file exists, an index is appended (e.g., rule_name-2.yml) to prevent overwriting.

### Step 9 – Present Final Rule
- Show the final validated rule in a ```yaml code block.
- Briefly explain what it detects and why the detection logic was chosen.
- Note known false positives and how to tune them.
- Suggest related detection ideas if applicable.

---

## Sigma Rule Format Reference

```yaml
title: <Short, specific description – max 256 chars>
id: <UUID v4 – must be present, generate with uuid.uuid4()>
status: experimental   # experimental | test | stable | deprecated
description: |
    Detects <what>. <Context about why this is suspicious>.
references:
    - https://example.com/source
author: Sigma AI
date: 2026-10-04          # YYYY-MM-DD
modified: 2026-10-04      # Update when you change the rule
tags:
    - attack.execution    # MITRE ATT&CK tactic (lowercase)
    - attack.t1059        # MITRE ATT&CK technique
    - attack.t1059.001    # Sub-technique
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\\\\suspicious.exe'
        CommandLine|contains: '-enc'
    filter_legitimate:
        ParentImage|endswith: '\\\\legitimate.exe'
    condition: selection and not filter_legitimate
fields:
    - Image
    - CommandLine
    - ParentImage
falsepositives:
    - Legitimate administrative scripts
    - Software updaters
level: medium             # informational | low | medium | high | critical
```

## Detection Engineering Rules

1. **Simplicity first**: A detection that catches 80% of cases reliably beats a complex one with false positives.
2. **Generic logsources**: Use `category: process_creation, product: windows` not `service: sysmon, EventID: 1`.
3. **OriginalFileName over Image**: Detects renamed binaries (e.g. `OriginalFileName: 'whoami.exe'`).
4. **Path modifiers**: Always use `Image|endswith: '\\\\tool.exe'` not `Image|contains: 'tool'`.
5. **Filter false positives**: Add a `filter_*` block for known-legitimate cases and negate it.
6. **CommandLine caution**: CommandLine is powerful but can be spoofed – combine with Image checks.
7. **No `all of them`**: Use `all of selection*` instead.
8. **Level calibration**: `high` only when clearly malicious and false positives are rare.
9. **MITRE tags**: Always add at least one `attack.<tactic>` and `attack.t<technique>` tag.
10. **UUID required**: Every rule must have a UUID v4 `id` field.
11. **Correlation rules**: If the detection requires counting events, distinct values, or
    temporal ordering across multiple events, consider a correlation rule. Call
    `get_correlation_rule_knowledge` **before** drafting any correlation rule to get the
    exact syntax — do not guess. Avoid correlation rules when a single-event rule suffices.

{LOGSOURCE_SUMMARY}

## Output Format for Final Rules
Present each completed rule in a fenced code block:
```yaml
# <Rule title>
<full YAML content>
```
Then provide a brief explanation (2–3 sentences) of the detection logic.
""".strip()


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def create_agent(config: dict[str, Any]) -> Agent:  # type: ignore[type-arg]
    model_name: str = config.get("model", "openai:gpt-4o")
    capabilities = _build_capabilities(model_name)
    model = _build_model(model_name)

    return Agent(
        model,
        instructions=_SYSTEM_PROMPT,
        capabilities=capabilities,
    )


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
    """Register all tools on the agent instance."""
    from sigma_ai.tools.sigma_output import save_rule as save_rule_to_file
    from sigma_ai.config import get_output_directory

    # Ensure config is properly captured in closure
    _config = config

    @agent.tool_plain
    async def fetch_url(url: str) -> str:
        """Fetch text content from a URL (web page or PDF). Returns the extracted text."""
        return await fetch_source(url)

    @agent.tool_plain
    def process_uploaded_pdf(content_base64: str) -> str:
        """Extract text from a base64-encoded PDF that was uploaded by the user.

        Pass the raw base64 string of the PDF file content.
        """
        import base64
        try:
            data = base64.b64decode(content_base64)
        except Exception as exc:  # noqa: BLE001
            return f"[Error] Could not decode base64 PDF data: {exc}"
        return extract_pdf_bytes(data)

    @agent.tool_plain
    def search_existing_rules(query: str) -> str:
        """Search the local SigmaHQ rule repository for existing rules similar to the query.

        Use this to check if a detection hypothesis is already covered.
        Returns a formatted list of matching rules with their titles, logsources, and tags.
        """
        results = search_rules(query)
        return format_results(results)

    @agent.tool_plain
    def validate_sigma_rule(rule_yaml: str) -> str:
        """Validate a Sigma rule YAML string using pySigma validators.

        Returns a validation summary with any issues found (HIGH = must fix, MEDIUM = should fix).
        Pass the complete YAML content of the rule.
        """
        result = validate_rule(rule_yaml)
        return result["summary"]

    @agent.tool_plain
    def get_logsource_info(activity_description: str) -> str:
        """Get information about relevant Sigma log sources for a given activity.

        Returns logsource definitions, available fields, common event IDs, and usage tips.
        Use this before drafting a rule to select the right logsource and fields.
        """
        return _get_logsource_info(activity_description)

    @agent.tool_plain
    def get_correlation_rule_knowledge() -> str:
        """Return the full Sigma correlation rules specification.

        Call this before drafting any correlation rule (event_count, value_count,
        temporal, temporal_ordered, value_sum, value_avg, value_percentile).
        It contains syntax, field names, examples, and common mistakes to avoid.
        """
        return _get_correlation_rules_spec()

    @agent.tool_plain
    def generate_rule_id() -> str:
        """Generate a fresh UUID v4 for use as a Sigma rule identifier.

        Always call this when creating a new rule to ensure a unique id field.
        """
        return str(uuid.uuid4())

    @agent.tool_plain
    def save_rule(rule_yaml: str) -> str:
        """Save a validated Sigma rule to a file in the output directory.

        The filename is automatically generated from the rule's title following
        SigmaHQ naming conventions. If a file with that name exists, an index
        is appended (e.g., rule_name-2.yml) to avoid overwriting existing files.

        Args:
            rule_yaml: The complete, validated YAML content of the Sigma rule.

        Returns:
            A confirmation message with the path where the rule was saved.
        """
        try:
            output_dir = get_output_directory(_config)
            return save_rule_to_file(rule_yaml, output_dir)
        except ValueError as e:
            return f"[Error] Could not save rule: {e}"
        except Exception as e:  # noqa: BLE001
            return f"[Error] Unexpected error saving rule: {e}"
