"""
Portable static-site fetcher.

The design document calls for `wget --mirror --convert-links --adjust-extension
--page-requisites --no-parent`. Windows doesn't ship wget, and PowerShell's
`wget` alias points at `Invoke-WebRequest` with different semantics, so this
module reimplements the mirror role in Python using `requests` +
`BeautifulSoup`. Link conversion is intentionally skipped — the MkDocs/spa
converters rewrite internal links themselves.

Usage:
    from ingest.fetchers.wget import fetch
    fetch(base_url="https://fastapi.tiangolo.com/", cache_dir=Path(...))
"""
from __future__ import annotations

import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()


def fetch(
    base_url: str,
    cache_dir: Path,
    *,
    exclude_pattern: str | None = None,
    max_pages: int = 5000,
    delay: float = 0.3,
    user_agent: str = "codex-ingest/0.1 (+https://github.com/codex)",
) -> Path:
    """
    Crawl ``base_url`` and save each reachable HTML page to ``cache_dir``,
    mirroring URL path structure. Returns the cache_dir.

    Stays on the same host and under the same path prefix as ``base_url``
    (the equivalent of ``wget --no-parent``).
    """
    cache_dir.mkdir(parents=True, exist_ok=True)

    base = base_url if base_url.endswith("/") else base_url + "/"
    parsed_base = urlparse(base)
    host = parsed_base.netloc
    path_prefix = parsed_base.path or "/"
    exclude_re = re.compile(exclude_pattern) if exclude_pattern else None

    session = requests.Session()
    session.headers["User-Agent"] = user_agent

    visited: set[str] = set()
    asset_visited: set[str] = set()
    queue: deque[str] = deque([base])
    fetched = 0
    skipped = 0
    excluded = 0
    assets = 0

    while queue and fetched < max_pages:
        url = queue.popleft()
        url, _ = urldefrag(url)
        if url in visited:
            continue
        visited.add(url)

        parsed = urlparse(url)
        if parsed.netloc != host:
            continue
        if not parsed.path.startswith(path_prefix):
            continue
        if exclude_re and exclude_re.search(parsed.path):
            excluded += 1
            continue

        try:
            resp = session.get(url, timeout=30, allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            console.log(f"[yellow]skip[/yellow] {url} ({e})")
            skipped += 1
            continue

        ctype = resp.headers.get("content-type", "")
        if "html" not in ctype.lower():
            continue

        rel = _url_to_path(parsed.path, path_prefix)
        out = cache_dir / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(resp.text, encoding="utf-8")
        fetched += 1
        if fetched % 25 == 0:
            console.log(f"  fetched {fetched} pages…")

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("mailto:", "javascript:", "tel:", "#")):
                continue
            absolute, _ = urldefrag(urljoin(url, href))
            if absolute not in visited:
                queue.append(absolute)

        # Pull page-requisites: images, stylesheets, scripts, icons.
        # Same-host only; these may live outside the docs `path_prefix`
        # (e.g. /assets/..., /img/...) so the no-parent constraint does
        # NOT apply.
        for el, attr in _asset_elements(soup):
            raw = el.get(attr)
            if not raw or raw.startswith(("data:", "//")):
                continue
            asset_url, _ = urldefrag(urljoin(url, raw))
            if asset_url in asset_visited:
                continue
            asset_visited.add(asset_url)
            asset_parsed = urlparse(asset_url)
            if asset_parsed.netloc != host or not asset_parsed.path:
                continue
            try:
                asset_resp = session.get(asset_url, timeout=30)
                asset_resp.raise_for_status()
            except requests.RequestException:
                continue
            asset_rel = asset_parsed.path.lstrip("/")
            if not asset_rel:
                continue
            asset_out = cache_dir / asset_rel
            asset_out.parent.mkdir(parents=True, exist_ok=True)
            asset_out.write_bytes(asset_resp.content)
            assets += 1

        time.sleep(delay)

    console.log(
        f"[bold green]fetched {fetched} pages[/bold green] from {base_url} "
        f"(assets {assets}, skipped {skipped}, excluded {excluded})"
    )
    return cache_dir


def _asset_elements(soup: BeautifulSoup):
    """Yield (element, attr_name) for every page-requisite reference."""
    for img in soup.find_all("img", src=True):
        yield img, "src"
    for link in soup.find_all("link", href=True):
        rels = link.get("rel") or []
        # Material/MkDocs frequently includes rel="stylesheet" and rel="icon"
        # plus rel="preload" rel="manifest" rel="alternate". Pull the visual
        # essentials only.
        if any(r in ("stylesheet", "icon", "shortcut icon", "apple-touch-icon", "mask-icon", "manifest") for r in rels):
            yield link, "href"
    for script in soup.find_all("script", src=True):
        yield script, "src"
    for source in soup.find_all("source", src=True):
        yield source, "src"


def _url_to_path(url_path: str, prefix: str) -> str:
    """Convert URL path to a filesystem-safe relative path ending in .html."""
    rel = url_path[len(prefix):] if url_path.startswith(prefix) else url_path
    rel = rel.lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel = rel + "index.html"
    elif "." not in Path(rel).name:
        rel = rel.rstrip("/") + "/index.html"
    return rel
