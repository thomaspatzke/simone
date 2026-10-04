"""Entry point: load config, ensure Sigma repo, start the web UI."""
from __future__ import annotations

import sys


def main() -> None:
    from sigma_ai.config import load_config, get_sigma_repo_path
    from sigma_ai.tools.sigma_repo import ensure_repo
    from sigma_ai.tools.sigma_search import initialize as init_search
    from sigma_ai.agent import create_agent, register_tools

    config = load_config()

    # Download Sigma rule repo if not already present
    repo_path = ensure_repo(config)

    # Build the in-memory search index
    init_search(repo_path)

    # Create agent and register tools
    agent = create_agent(config)
    register_tools(agent)

    # Build list of additional models for the UI model selector
    extra_models: list[str] = config.get("extra_models", [])

    app = agent.to_web(
        models=extra_models if extra_models else None,
    )

    host: str = config.get("server", {}).get("host", "127.0.0.1")
    port: int = config.get("server", {}).get("port", 7932)

    try:
        import uvicorn  # type: ignore[import-untyped]
    except ImportError:
        print("[error] uvicorn is not installed. Run: uv sync", file=sys.stderr)
        sys.exit(1)

    print(f"\n✅  Sigma AI is running → http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
