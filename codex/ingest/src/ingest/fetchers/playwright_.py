"""SPA crawler using Playwright.

For JS-rendered sites (React, Next.js docs) we can't just hit URLs — the
content lives in client-side templates that only fill in after the page's
JavaScript runs. This fetcher launches a headless Chromium, waits for each
page's content selector to appear, then captures the fully-rendered DOM.

Scripts are stripped from saved HTML so client-side routing/hydration
doesn't interfere with the static iframe view. The visible content survives;
the SPA's own navigation becomes plain `<a>` links again.

Page-requisite assets (CSS, JS, images, fonts referenced via `<link>` etc.)
are downloaded after the crawl via the shared curl_cffi HTTP client.
"""
from __future__ import annotations

import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup
from rich.console import Console

try:
    from curl_cffi import requests as http_client  # type: ignore
    _IMPERSONATE = "chrome131"
except ImportError:  # pragma: no cover
    import requests as http_client  # type: ignore
    _IMPERSONATE = None

console = Console()


def _import_playwright():
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        return sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright is not installed. Run: "
            "`uv pip install -e .[spa] && playwright install chromium`"
        ) from e


def fetch(
    base_url: str,
    cache_dir: Path,
    *,
    start_paths: list[str],
    url_pattern: str,
    content_selector: str = "",
    exclude_pattern: str | None = None,
    max_pages: int = 5000,
    delay: float = 0.6,
) -> Path:
    """Crawl an SPA, render each page with Chromium, save the static DOM."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    parsed_base = urlparse(base_url)
    host = parsed_base.netloc
    path_prefix = parsed_base.path.rstrip("/") + "/" if parsed_base.path else "/"
    pattern_re = re.compile(url_pattern)
    exclude_re = re.compile(exclude_pattern) if exclude_pattern else None

    visited: set[str] = set()
    asset_urls: set[str] = set()
    queue: deque[str] = deque()

    origin = f"{parsed_base.scheme}://{host}"
    for p in start_paths:
        queue.append(urljoin(origin + "/", p.lstrip("/")))

    sync_playwright = _import_playwright()
    fetched = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            # Match Codex's dark shell so SPA snapshots use the upstream
            # site's dark theme (these are captured statically — we can't
            # toggle theme inside the iframe later).
            color_scheme="dark",
        )
        page = context.new_page()

        while queue and fetched < max_pages:
            url = queue.popleft()
            url, _ = urldefrag(url)
            if url in visited:
                continue
            visited.add(url)

            parsed = urlparse(url)
            if parsed.netloc != host:
                continue
            if not pattern_re.search(parsed.path):
                continue
            if exclude_re and exclude_re.search(parsed.path):
                continue

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                console.log(f"[yellow]skip[/yellow] {url} ({e.__class__.__name__})")
                continue
            # If a content selector was explicitly configured, wait for it
            # (with a short timeout — we don't want it to dominate crawl time).
            # Otherwise rely on networkidle to mark hydration as complete.
            if content_selector:
                try:
                    page.wait_for_selector(content_selector, timeout=4000)
                except Exception:
                    pass
            else:
                try:
                    page.wait_for_load_state("networkidle", timeout=4000)
                except Exception:
                    pass

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # Discover internal links BEFORE stripping scripts.
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith(("mailto:", "javascript:", "tel:", "#")):
                    continue
                absolute, _ = urldefrag(urljoin(url, href))
                # Skip alternate-view URLs that aren't HTML pages (Next.js
                # exposes .md sources, .json metadata, .txt views, etc.).
                if absolute.endswith((".md", ".mdx", ".txt", ".json", ".xml")):
                    continue
                if absolute not in visited:
                    queue.append(absolute)

            # Collect asset URLs (CSS/JS/images/icons) referenced by this page.
            for tag, attr in _asset_elements(soup):
                raw = tag.get(attr)
                if not raw or raw.startswith(("data:", "//")):
                    continue
                abs_url, _ = urldefrag(urljoin(url, raw))
                if urlparse(abs_url).netloc == host:
                    asset_urls.add(abs_url)

            # Strip scripts so the saved snapshot doesn't try to client-side
            # route or re-hydrate inside our iframe.
            for s in soup.find_all("script"):
                s.decompose()
            # Inject an early-paint dark background + color-scheme meta so the
            # browser's initial canvas is dark before the page's own CSS loads.
            # Without this, every iframe navigation flashes white briefly.
            if soup.head:
                early_style = soup.new_tag("style")
                early_style.string = (
                    "html,body{background:#1a1a1a;color-scheme:dark}"
                )
                soup.head.insert(0, early_style)
                cs_meta = soup.new_tag(
                    "meta", attrs={"name": "color-scheme", "content": "dark"}
                )
                soup.head.insert(0, cs_meta)
            # Drop responsive `srcset` variants — most aren't in our cache and
            # the browser would otherwise pick a non-existent URL. Falling back
            # to the plain `src` (which we did download) makes images appear.
            for img in soup.find_all("img"):
                if img.has_attr("srcset"):
                    del img["srcset"]
                if img.has_attr("loading"):
                    del img["loading"]
            for source in soup.find_all("source"):
                if source.has_attr("srcset"):
                    del source["srcset"]
            saved_html = str(soup)

            rel = _url_to_path(parsed.path, path_prefix)
            out = cache_dir / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(saved_html, encoding="utf-8")
            fetched += 1
            if fetched % 25 == 0:
                console.log(f"  fetched {fetched} pages…")

            time.sleep(delay)

        browser.close()

    # If we crawled start paths under e.g. /learn and /reference/react but no
    # /index.html exists in cache, write a redirect stub so the iframe's
    # initial load (/sources/<name>/) lands on the first start path.
    if not (cache_dir / "index.html").exists() and start_paths:
        first_rel = _url_to_path(start_paths[0], path_prefix)
        first_rel = first_rel.removesuffix("/index.html")
        landing = f"{first_rel}/" if first_rel else "./"
        (cache_dir / "index.html").write_text(
            f'<!doctype html><meta http-equiv="refresh" content="0; url={landing}">\n',
            encoding="utf-8",
        )

    assets = _download_assets(asset_urls, cache_dir, path_prefix)
    console.log(
        f"[bold green]fetched {fetched} pages[/bold green] from {base_url} "
        f"(assets {assets})"
    )
    return cache_dir


def _url_to_path(url_path: str, prefix: str) -> str:
    if url_path.startswith(prefix):
        rel = url_path[len(prefix):]
    elif prefix.endswith("/") and url_path == prefix.rstrip("/"):
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


def _asset_elements(soup: BeautifulSoup):
    for img in soup.find_all("img", src=True):
        yield img, "src"
    for link in soup.find_all("link", href=True):
        rels = link.get("rel") or []
        # `preload` covers Next.js-style font preloads (rel="preload" as="font").
        # Without it the page renders with system-font fallbacks.
        if any(
            r in ("stylesheet", "icon", "shortcut icon", "apple-touch-icon", "mask-icon", "manifest", "preload")
            for r in rels
        ):
            yield link, "href"
    for script in soup.find_all("script", src=True):
        yield script, "src"
    for source in soup.find_all("source", src=True):
        yield source, "src"


def _download_assets(urls: set[str], cache_dir: Path, path_prefix: str) -> int:
    if not urls:
        return 0
    # curl_cffi's Chrome impersonation enforces TLS — it can fail against
    # plain-HTTP localhost (used when crawling a locally-built Next.js site
    # instead of the public origin). Detect that case and skip impersonation.
    is_localhost = any(
        urlparse(u).hostname in ("localhost", "127.0.0.1", "::1") for u in urls
    )
    if _IMPERSONATE and not is_localhost:
        session = http_client.Session(impersonate=_IMPERSONATE)
    else:
        session = http_client.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    })

    count = 0
    failures: list[tuple[str, str]] = []
    for url in urls:
        parsed = urlparse(url)
        asset_path = parsed.path
        if asset_path.startswith(path_prefix):
            asset_path = asset_path[len(path_prefix):]
        rel = asset_path.lstrip("/")
        if not rel:
            continue
        out = cache_dir / rel
        if out.exists():
            continue
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            failures.append((url, f"{e.__class__.__name__}: {e}"))
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(resp.content)
        count += 1
    if failures:
        console.log(
            f"[yellow]asset download failures: {len(failures)} / {len(urls)}[/yellow]"
        )
        for url, err in failures[:5]:
            console.log(f"  [dim]{url}[/dim] — {err}")
    return count
