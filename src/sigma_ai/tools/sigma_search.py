"""Search the local SigmaHQ rule cache for existing detection rules."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Module-level cache: populated on first call to search_rules()
_index: list[dict[str, Any]] = []
_repo_path: Path | None = None


def initialize(repo_path: Path) -> None:
    """Pre-load the rule index (called at startup after repo is available)."""
    global _repo_path
    _repo_path = repo_path
    _build_index(repo_path)


def search_rules(query: str, max_results: int = 12) -> list[dict[str, Any]]:
    """Search the local rule cache for rules matching the query string."""
    if not _index and _repo_path is not None:
        _build_index(_repo_path)

    if not _index:
        return []

    keywords = [kw.lower() for kw in query.split() if len(kw) > 2]
    if not keywords:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in _index:
        score = _score(entry, keywords)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:max_results]]


def format_results(results: list[dict[str, Any]]) -> str:
    """Return a human-readable summary of search results."""
    if not results:
        return "No similar rules found in the SigmaHQ repository."

    lines = [f"Found {len(results)} similar rule(s) in SigmaHQ:\n"]
    for r in results:
        ls = r.get("logsource", {})
        ls_str = ", ".join(f"{k}: {v}" for k, v in ls.items() if v)
        tags = ", ".join(r.get("tags", [])[:4])
        lines.append(f"**{r['title']}**")
        lines.append(f"  - Status: {r.get('status', 'unknown')} | Level: {r.get('level', '?')} | Logsource: {ls_str}")
        if tags:
            lines.append(f"  - Tags: {tags}")
        if desc := r.get("description"):
            lines.append(f"  - {desc[:150].strip()}…" if len(desc) > 150 else f"  - {desc.strip()}")
        lines.append(f"  - File: {r.get('path', '')}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_index(repo_path: Path) -> None:
    global _index
    if not repo_path.exists():
        return

    entries: list[dict[str, Any]] = []
    for yml_file in repo_path.rglob("*.yml"):
        entry = _parse_rule_file(yml_file)
        if entry is not None:
            entries.append(entry)

    _index = entries
    print(f"[sigma-search] Indexed {len(_index)} rules from {repo_path}")


def _parse_rule_file(path: Path) -> dict[str, Any] | None:
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict) or "title" not in data:
            return None
        return {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "status": data.get("status", ""),
            "level": data.get("level", ""),
            "logsource": data.get("logsource", {}),
            "tags": data.get("tags", []),
            "author": data.get("author", ""),
            # Searchable text blob
            "_text": (
                f"{data.get('title', '')} "
                f"{data.get('description', '')} "
                f"{' '.join(data.get('tags', []))} "
                f"{str(data.get('logsource', {}))}"
            ).lower(),
            "path": str(path.relative_to(path.parent.parent.parent) if path.parent.parent.parent.exists() else path.name),
        }
    except Exception:  # noqa: BLE001
        return None


def _score(entry: dict[str, Any], keywords: list[str]) -> int:
    text = entry.get("_text", "")
    title = entry.get("title", "").lower()
    tags = " ".join(entry.get("tags", [])).lower()

    score = 0
    for kw in keywords:
        if kw in title:
            score += 3
        elif kw in tags:
            score += 2
        elif kw in text:
            score += 1
    return score
