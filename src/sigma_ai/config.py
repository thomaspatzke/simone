"""Configuration loading: reads config.yaml and sets provider API keys as env vars."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Maps config key → environment variable expected by pydantic-ai providers
_PROVIDER_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "together": "TOGETHER_API_KEY",
    "cohere": "CO_API_KEY",
}

_DEFAULT_CONFIG: dict[str, Any] = {
    "model": "openai:gpt-4o",
    "api_keys": {},
    "extra_models": [],
    "sigma_repo": {
        "path": "~/.sigma-ai/sigma-rules",
        "auto_update": False,
    },
    "output": {
        "directory": "~/.sigma-ai/generated-rules",
    },
    "server": {
        "host": "127.0.0.1",
        "port": 7932,
    },
}


def load_config(path: str = "config.yaml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        print(
            f"[config] No config.yaml found at '{path}'. "
            "Copy config.yaml.example to config.yaml and add your API keys."
        )
        config = _DEFAULT_CONFIG.copy()
    else:
        with config_path.open(encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        config = _deep_merge(_DEFAULT_CONFIG, loaded)

    _apply_api_keys(config.get("api_keys", {}))
    return config


def get_sigma_repo_path(config: dict[str, Any]) -> Path:
    raw = config.get("sigma_repo", {}).get("path", "~/.sigma-ai/sigma-rules")
    return Path(raw).expanduser().resolve()


def get_output_directory(config: dict[str, Any]) -> Path:
    raw = config.get("output", {}).get("directory", "~/.sigma-ai/generated-rules")
    return Path(raw).expanduser().resolve()


def _apply_api_keys(keys: dict[str, str]) -> None:
    for provider, value in keys.items():
        if value and (env_var := _PROVIDER_ENV_VARS.get(provider)):
            os.environ.setdefault(env_var, value)


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
