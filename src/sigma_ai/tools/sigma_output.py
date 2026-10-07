"""Save Sigma rules to files following SigmaHQ naming conventions with auto-indexing."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


def extract_sigma_filename(rule_yaml: str) -> str:
    """Extract a Sigma filename from the rule title following SigmaHQ conventions.

    The filename is derived from the rule's title field in the YAML.
    - Convert to lowercase
    - Replace spaces and special characters with underscores
    - Append .yml extension

    Args:
        rule_yaml: Complete YAML content of the Sigma rule.

    Returns:
        A filename following Sigma conventions (e.g., "rule_title_example.yml").

    Raises:
        ValueError: If the rule has no title or cannot be parsed.
    """
    try:
        rule = yaml.safe_load(rule_yaml)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}") from e

    if not isinstance(rule, dict) or "title" not in rule:
        raise ValueError("Rule must contain a 'title' field")

    title = rule["title"].strip()
    if not title:
        raise ValueError("Rule title cannot be empty")

    # Convert title to filename: lowercase, spaces/special chars → underscores
    filename = re.sub(r"[^\w\s]", "", title)  # Remove special chars
    filename = re.sub(r"\s+", "_", filename)  # Replace spaces with underscores
    filename = filename.lower()

    return f"{filename}.yml"


def find_next_available_path(output_dir: Path, base_filename: str) -> Path:
    """Find the next available file path by appending an index if necessary.

    If the file doesn't exist, return it as-is.
    If it does exist, append an index before the extension (e.g., filename-2.yml).
    Increments the index until an available path is found.

    Args:
        output_dir: Directory where the file should be saved.
        base_filename: Base filename (e.g., "rule_title.yml").

    Returns:
        A Path object pointing to an available file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    target_path = output_dir / base_filename
    if not target_path.exists():
        return target_path

    # File exists; append index
    name_parts = base_filename.rsplit(".", 1)
    if len(name_parts) == 2:
        stem, ext = name_parts
    else:
        stem, ext = base_filename, ""

    index = 2
    while True:
        indexed_filename = f"{stem}-{index}.{ext}" if ext else f"{stem}-{index}"
        candidate_path = output_dir / indexed_filename
        if not candidate_path.exists():
            return candidate_path
        index += 1


def save_rule(rule_yaml: str, output_dir: Path) -> str:
    """Save a Sigma rule to a file in the output directory.

    The filename is generated from the rule's title following SigmaHQ conventions.
    If a file with that name already exists, an index is appended to avoid overwriting.

    Args:
        rule_yaml: Complete YAML content of the Sigma rule.
        output_dir: Directory where the rule should be saved.

    Returns:
        A message indicating where the rule was saved.

    Raises:
        ValueError: If the rule is invalid or has no title.
    """
    base_filename = extract_sigma_filename(rule_yaml)
    target_path = find_next_available_path(output_dir, base_filename)

    target_path.write_text(rule_yaml, encoding="utf-8")

    return f"✅ Rule saved to: {target_path.as_posix()}"
