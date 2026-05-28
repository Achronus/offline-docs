"""Build a per-source search index from staged HTML.

Walks every ``*.html`` file under a source's staged directory and emits
``_codex_search.json`` — a flat list of ``{url, title, headings, snippet}``
entries the in-iframe search widget (``static/codex-search.js``) consumes.

Only used for sources marked ``custom_search: true`` in codex.yaml — typically
ones whose native search is cloud-only (React, Next.js).
"""
from __future__ import annotations

import json
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console

console = Console()


def build_index(source_dir: Path, source_name: str | None = None) -> list[dict]:
    """Walk ``source_dir`` and return a list of search entries.

    URLs are emitted as absolute paths anchored under ``/sources/<source>/``
    so they resolve correctly when the search widget is opened on a nested
    page (otherwise a ``./foo/`` URL would resolve relative to the current
    document, not the source root).
    """
    if source_name is None:
        source_name = source_dir.name
    url_root = f"/sources/{source_name}/"
    entries: list[dict] = []
    for html_path in sorted(source_dir.rglob("*.html")):
        rel = html_path.relative_to(source_dir)
        url = url_root + _entry_url(rel).lstrip("./")
        try:
            text = html_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        soup = BeautifulSoup(text, "html.parser")
        for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        title = _extract_title(soup)
        if not title:
            continue
        headings = _extract_headings(soup)
        snippet = _extract_snippet(soup)

        entries.append({
            "url": url,
            "title": title,
            "headings": headings,
            "snippet": snippet,
        })

    return entries


def write_index(source_dir: Path, source_name: str | None = None) -> Path:
    """Build and serialise ``_codex_search.json`` for ``source_dir``."""
    entries = build_index(source_dir, source_name)
    out = source_dir / "_codex_search.json"
    out.write_text(
        json.dumps(entries, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return out


def _entry_url(rel: Path) -> str:
    parts = rel.parts
    # foo/bar/index.html → foo/bar/
    if parts and parts[-1] == "index.html":
        parts = parts[:-1]
        return "/".join(parts) + ("/" if parts else "")
    return "/".join(parts)


def _extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    if soup.title and soup.title.string:
        # Trim common "  — Project" suffixes.
        return soup.title.get_text(strip=True).split(" — ")[0].split(" | ")[0]
    return ""


def _extract_headings(soup: BeautifulSoup, limit: int = 8) -> list[str]:
    out: list[str] = []
    for h in soup.find_all(["h2", "h3"]):
        text = h.get_text(strip=True)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _extract_snippet(soup: BeautifulSoup, max_chars: int = 200) -> str:
    main = soup.find("main") or soup.find("article") or soup.body
    if not main:
        return ""
    for p in main.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) >= 20:
            return text[:max_chars].rstrip() + ("…" if len(text) > max_chars else "")
    return ""
