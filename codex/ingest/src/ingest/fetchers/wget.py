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
    img_visited: set[str] = set()
    queue: deque[str] = deque([base])
    fetched = 0
    skipped = 0
    excluded = 0
    images = 0

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

        # Pull image assets referenced by this page. Same-host only; assets
        # may live outside the docs `path_prefix` (e.g. /img/...) so we do
        # NOT apply the no-parent constraint here.
        for img in soup.find_all("img", src=True):
            src = img["src"]
            if src.startswith(("data:", "//")):
                continue
            img_url, _ = urldefrag(urljoin(url, src))
            if img_url in img_visited:
                continue
            img_visited.add(img_url)
            img_parsed = urlparse(img_url)
            if img_parsed.netloc != host or not img_parsed.path:
                continue
            try:
                img_resp = session.get(img_url, timeout=30)
                img_resp.raise_for_status()
            except requests.RequestException:
                continue
            img_rel = img_parsed.path.lstrip("/")
            if not img_rel:
                continue
            img_out = cache_dir / img_rel
            img_out.parent.mkdir(parents=True, exist_ok=True)
            img_out.write_bytes(img_resp.content)
            images += 1

        time.sleep(delay)

    console.log(
        f"[bold green]fetched {fetched} pages[/bold green] from {base_url} "
        f"(images {images}, skipped {skipped}, excluded {excluded})"
    )
    return cache_dir


def _url_to_path(url_path: str, prefix: str) -> str:
    """Convert URL path to a filesystem-safe relative path ending in .html."""
    rel = url_path[len(prefix):] if url_path.startswith(prefix) else url_path
    rel = rel.lstrip("/")
    if rel == "" or rel.endswith("/"):
        rel = rel + "index.html"
    elif "." not in Path(rel).name:
        rel = rel.rstrip("/") + "/index.html"
    return rel
