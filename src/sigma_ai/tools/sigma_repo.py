"""Download and manage a local cache of the SigmaHQ/sigma rule repository."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

_SIGMA_ZIP_URL = "https://codeload.github.com/SigmaHQ/sigma/zip/refs/heads/master"
_MARKER_FILE = ".downloaded"


def ensure_repo(config: dict[str, Any]) -> Path:
    """Ensure the local Sigma rule cache exists; download if missing."""
    from sigma_ai.config import get_sigma_repo_path  # avoid circular at module level

    repo_path = get_sigma_repo_path(config)
    auto_update = config.get("sigma_repo", {}).get("auto_update", False)

    if not (repo_path / _MARKER_FILE).exists() or auto_update:
        _download(repo_path)

    return repo_path


def _download(dest: Path) -> None:
    import httpx  # lazy import so tests can mock it

    print(f"[sigma-repo] Downloading SigmaHQ rule repository to {dest} …")
    print("[sigma-repo] This may take a moment (first run only).")

    try:
        with httpx.Client(follow_redirects=True, timeout=120.0) as client:
            response = client.get(_SIGMA_ZIP_URL)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"[sigma-repo] WARNING: Could not download Sigma rules: {exc}")
        print("[sigma-repo] Rule deduplication check will be unavailable.")
        return

    dest.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            rule_entries = [
                name for name in zf.namelist()
                if name.endswith(".yml") and "/rules" in name and not name.endswith("/")
            ]
            for entry in rule_entries:
                # Strip the top-level "sigma-master/" prefix from paths
                parts = Path(entry).parts
                if len(parts) < 2:
                    continue
                rel_path = Path(*parts[1:])  # drop "sigma-master"
                out_file = dest / rel_path
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_bytes(zf.read(entry))

        (dest / _MARKER_FILE).write_text("ok", encoding="utf-8")
        print(f"[sigma-repo] Downloaded {len(rule_entries)} rule files.")
    except zipfile.BadZipFile as exc:
        print(f"[sigma-repo] WARNING: Downloaded file is not a valid ZIP: {exc}")


def get_rule_files(repo_path: Path) -> list[Path]:
    """Return all YAML rule files in the cached repository."""
    if not repo_path.exists():
        return []
    return list(repo_path.rglob("*.yml"))
