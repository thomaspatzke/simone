"""Save Sigma rules to files without overwriting existing ones.

File names come from the Sigma MCP server's ``suggest_rule_filename`` tool,
which applies the SigmaHQ naming conventions.  This module only checks that a
name is a plain SigmaHQ-style file name and never overwrites a file.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

_FILENAME = re.compile(r"[a-z0-9_]+\.yml")


def check_filename(filename: str) -> str:
    """Return *filename* if it is a plain SigmaHQ-style rule file name.

    Only ``a-z``, ``0-9`` and ``_`` followed by ``.yml`` are accepted, which
    also rules out directories and ``..``.

    Raises:
        ValueError: The name does not match.
    """
    if not _FILENAME.fullmatch(filename):
        raise ValueError(
            f"Invalid file name {filename!r}: use the name from suggest_rule_filename "
            "(only a-z, 0-9 and _, ending in .yml)."
        )
    return filename


def find_next_available_path(output_dir: Path, filename: str) -> Path:
    """Return *output_dir*/*filename*, or the first free ``<stem>_<n>.yml``.

    The suffix uses an underscore because SigmaHQ file names must not contain
    hyphens.  The directory is created if needed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / filename
    if not target.exists():
        return target
    stem, suffix = filename.rsplit(".", 1)
    index = 2
    while (candidate := output_dir / f"{stem}_{index}.{suffix}").exists():
        index += 1
    return candidate


def save_rule(rule_yaml: str, filename: str, output_dir: Path) -> str:
    """Save *rule_yaml* as *filename* in *output_dir* without overwriting.

    Returns:
        A message with the path the rule was saved to.

    Raises:
        ValueError: The file name is invalid or the YAML cannot be parsed.
    """
    check_filename(filename)
    try:
        documents = [d for d in yaml.safe_load_all(rule_yaml) if d is not None]
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc
    if not documents:
        raise ValueError("The rule YAML is empty.")
    target = find_next_available_path(output_dir, filename)
    target.write_text(rule_yaml, encoding="utf-8")
    return f"✅ Rule saved to: {target.as_posix()}"
