"""Entry point: load config, ensure Sigma repo, start the web UI."""
from __future__ import annotations

import sys

_BRANDING_SCRIPT = (
    b'<script>'
    b'document.title="simone";'
    b'function _simonePatch(){'
    b'  var w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,null,false),n;'
    b'  while(n=w.nextNode())if(n.nodeValue==="Pydantic AI")n.nodeValue="simone";'
    b'}'
    b'document.addEventListener("DOMContentLoaded",function(){'
    b'  _simonePatch();'
    b'  new MutationObserver(_simonePatch).observe(document.body,{childList:true,subtree:true});'
    b'});'
    b'</script>'
)


class _BrandingMiddleware:
    """ASGI middleware that rewrites the chat UI HTML to show 'simone' branding."""

    def __init__(self, inner_app) -> None:
        self._inner = inner_app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self._inner(scope, receive, send)
            return

        body_parts: list[bytes] = []
        is_html = False
        start_message: dict = {}

        async def patched_send(message) -> None:
            nonlocal is_html, start_message
            if message["type"] == "http.response.start":
                headers = {k.lower(): v for k, v in message.get("headers", [])}
                is_html = b"text/html" in headers.get(b"content-type", b"")
                start_message = message
                if not is_html:
                    await send(message)
            elif message["type"] == "http.response.body":
                if not is_html:
                    await send(message)
                    return
                body_parts.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                body = b"".join(body_parts)
                body = body.replace(
                    b"<title>Pydantic AI</title>",
                    b"<title>simone</title>",
                ).replace(b"</head>", _BRANDING_SCRIPT + b"</head>", 1)
                patched_headers = [
                    (k, v)
                    for k, v in start_message["headers"]
                    if k.lower() != b"content-length"
                ]
                patched_headers.append((b"content-length", str(len(body)).encode()))
                await send({**start_message, "headers": patched_headers})
                await send({"type": "http.response.body", "body": body, "more_body": False})
            else:
                await send(message)

        await self._inner(scope, receive, patched_send)


def main() -> None:
    from simone.config import load_config, get_sigma_repo_path
    from simone.tools.sigma_repo import ensure_repo
    from simone.tools.sigma_search import initialize as init_search
    from simone.agent import create_agent, register_tools

    config = load_config()

    # Download Sigma rule repo if not already present
    repo_path = ensure_repo(config)

    # Build the in-memory search index
    init_search(repo_path)

    # Create agent and register tools
    agent = create_agent(config)
    register_tools(agent, config)

    # Build list of additional models for the UI model selector
    extra_models: list[str] = config.get("extra_models", [])

    _raw_app = agent.to_web(
        models=extra_models if extra_models else None,
    )
    app = _BrandingMiddleware(_raw_app)

    host: str = config.get("server", {}).get("host", "127.0.0.1")
    port: int = config.get("server", {}).get("port", 7932)

    try:
        import uvicorn  # type: ignore[import-untyped]
    except ImportError:
        print("[error] uvicorn is not installed. Run: uv sync", file=sys.stderr)
        sys.exit(1)

    print(f"\n✅  simone is running → http://{host}:{port}\n")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
