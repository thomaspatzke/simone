"""Fetch text content from URLs: handles HTML pages and PDFs."""
from __future__ import annotations

import io
import re

import httpx

_MAX_CHARS = 25_000
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf,*/*",
}


async def fetch_source(url: str) -> str:
    """Fetch a URL and return its text content (HTML stripped, PDF extracted)."""
    try:
        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return f"[Error] HTTP {exc.response.status_code} fetching {url}"
    except httpx.RequestError as exc:
        return f"[Error] Network error fetching {url}: {exc}"

    content_type = response.headers.get("content-type", "").lower()

    if "pdf" in content_type or url.lower().endswith(".pdf"):
        return _extract_pdf(response.content, url)
    return _extract_html(response.text, url)


def extract_pdf_bytes(data: bytes) -> str:
    """Extract text from PDF bytes (for uploaded files)."""
    return _extract_pdf(data, source="<uploaded PDF>")


def _extract_pdf(data: bytes, source: str) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-untyped]
    except ImportError:
        return "[Error] pypdf not installed – cannot extract PDF text"

    try:
        reader = PdfReader(io.BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        full_text = "\n\n".join(pages)
        return _truncate(full_text, source)
    except Exception as exc:  # noqa: BLE001
        return f"[Error] Could not parse PDF from {source}: {exc}"


def _extract_html(html: str, source: str) -> str:
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]

        soup = BeautifulSoup(html, "lxml")
        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
    except Exception:  # noqa: BLE001
        # Fallback: strip HTML tags with regex
        text = re.sub(r"<[^>]+>", " ", html)

    # Collapse excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return _truncate(text.strip(), source)


def _truncate(text: str, source: str) -> str:
    if len(text) <= _MAX_CHARS:
        return text
    return text[:_MAX_CHARS] + f"\n\n[... truncated at {_MAX_CHARS} chars from {source}]"
