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

# curl_cffi impersonates a real Chrome's TLS handshake + HTTP/2 header order
# so Cloudflare-protected docs sites (most ReadTheDocs sources) don't 403 us.
# Falls back to plain requests if curl_cffi isn't installed.
try:
    from curl_cffi import requests as http_client  # type: ignore
    # Use a specific recent Chrome version target — generic "chrome" sometimes
    # fails CF's stricter zones (Optax, others).
    _IMPERSONATE = "chrome131"
except ImportError:  # pragma: no cover
    import requests as http_client  # type: ignore
    _IMPERSONATE = None
import requests as _requests_for_exc  # exception types regardless of client

# Catch both libs' HTTP exception classes so we cleanly skip individual failures
# regardless of which underlying client is in use.
try:
    from curl_cffi.requests.exceptions import RequestsError as _CurlRequestsError  # type: ignore
    _HTTP_EXCEPTIONS: tuple[type[BaseException], ...] = (
        _requests_for_exc.RequestException,
        _CurlRequestsError,
    )
except ImportError:
    _HTTP_EXCEPTIONS = (_requests_for_exc.RequestException,)
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
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
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

    session = (
        http_client.Session(impersonate=_IMPERSONATE)
        if _IMPERSONATE
        else http_client.Session()
    )
    # Some sites (RTD-hosted ones behind Cloudflare especially) reject barely-
    # shaped clients with a 403. Sending the same headers a real browser would
    # use clears the challenge.
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "DNT": "1",
        "Connection": "keep-alive",
    })

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
        except Exception as e:
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

        # Some Sphinx projects make their landing page a meta-refresh redirect
        # (e.g. MuJoCo's index → overview.html). Follow the target so the
        # crawler doesn't dead-end on the first page.
        meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile("^refresh$", re.I)})
        if meta_refresh:
            content = meta_refresh.get("content") or ""
            m = re.search(r"url\s*=\s*([^;\s]+)", content, re.IGNORECASE)
            if m:
                target, _ = urldefrag(urljoin(url, m.group(1)))
                if target not in visited:
                    queue.append(target)

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith(("mailto:", "javascript:", "tel:", "#")):
                continue
            absolute, _ = urldefrag(urljoin(url, href))
            # Sphinx links its raw .rst/.ipynb sources under /_sources/ for the
            # "View source" widget. RTD returns 403 for them and we don't need
            # them in the offline mirror — the rendered HTML is enough.
            if "/_sources/" in absolute or absolute.endswith((".rst", ".ipynb")):
                continue
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
            except Exception:
                continue
            # Mirror the same prefix-stripping we do for HTML pages so that
            # cached asset paths match what the HTML's relative refs expect.
            # Assets outside the docs path prefix (e.g. /img/sponsors on a
            # site whose docs live at /) keep their full path.
            asset_path = asset_parsed.path
            if asset_path.startswith(path_prefix):
                asset_path = asset_path[len(path_prefix):]
            asset_rel = asset_path.lstrip("/")
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

    # Playwright completion pass: capture dynamically-loaded resources
    # (web workers, JSON search indexes, lazy chunks) that wget's HTML scrape
    # never sees because they're requested at runtime from JS.
    try:
        captured = _playwright_completion_pass(base_url, cache_dir, host, path_prefix)
        if captured:
            console.log(f"[dim]+ {captured} dynamic assets via browser pass[/dim]")
    except Exception as e:
        console.log(f"[yellow]completion pass skipped: {e}[/yellow]")

    return cache_dir


def _playwright_completion_pass(base_url: str, cache_dir: Path, host: str, path_prefix: str) -> int:
    """Open the homepage in a real browser, snapshot any same-host responses
    that aren't already cached. Catches webpack-style chunked workers, search
    indexes, and other JS-fetched resources wget misses.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return 0

    captured = 0

    def on_response(response):
        nonlocal captured
        try:
            url = response.url
            status = response.status
            if status >= 400:
                return
            parsed = urlparse(url)
            if parsed.netloc != host or not parsed.path:
                return
            asset_path = parsed.path
            if asset_path.startswith(path_prefix):
                asset_path = asset_path[len(path_prefix):]
            rel = asset_path.lstrip("/")
            if not rel:
                return
            # Don't overwrite HTML pages (wget handled those) or files we
            # already have.
            out = cache_dir / rel
            if out.exists():
                return
            ctype = (response.headers.get("content-type") or "").lower()
            if "text/html" in ctype and not rel.endswith((".json", ".js", ".css", ".svg")):
                return
            body = response.body()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(body)
            captured += 1
        except Exception:
            return

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.on("response", on_response)
        try:
            page.goto(base_url, wait_until="networkidle", timeout=20000)
            # Some sites only fetch the search index on first interaction —
            # try to nudge it by focusing search-like elements.
            page.wait_for_timeout(800)
        except Exception:
            pass
        browser.close()

    return captured


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
    """Convert URL path to a filesystem-safe relative path ending in .html.

    Treats only ``.html``/``.htm`` suffixes as literal file URLs; any other
    pageish URL — including paths with dots in them like ``/docs/3.9.2``
    (Docusaurus version landing pages) — is stored as a directory landing
    (``<path>/index.html``).
    """
    if url_path.startswith(prefix):
        rel = url_path[len(prefix):]
    elif prefix.endswith("/") and url_path == prefix.rstrip("/"):
        # URL == prefix without trailing slash (e.g. "/docs" when prefix is
        # "/docs/"). Treat as the root landing.
        rel = ""
    else:
        rel = url_path
    rel = rel.lstrip("/")
    if rel == "":
        return "index.html"
    if rel.endswith("/"):
        return rel + "index.html"
    suffix = Path(rel).suffix.lower()
    if suffix in (".html", ".htm"):
        return rel
    return rel + "/index.html"
