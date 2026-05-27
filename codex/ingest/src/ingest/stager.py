"""Stage a fetched cache directory into the site's static tree for iframe
rendering.

We keep each source's native HTML untouched in structure, just rewriting
root-relative URLs (``/foo``) to live under ``/sources/<source>/`` so that
when the page is loaded inside the Codex iframe (whose URL is
``/sources/<source>/...``) every internal reference resolves correctly.

Document-relative (``./foo`` / ``../foo``) and absolute external URLs pass
through unchanged.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from rich.console import Console

console = Console()

# Matches the value of href/src/etc. attributes in HTML. Captures the quote
# character so we can reinsert it unchanged. We deliberately only rewrite
# root-relative paths (start with `/`, but not `//` for protocol-relative).
_URL_ATTR_RE = re.compile(
    r"""\s(href|src|action|formaction|poster|data)=(['"])(/(?!/)[^'"]*)\2""",
    re.IGNORECASE,
)

# Inside <style>...</style> and CSS files, url(...) can carry root-relative refs too.
_CSS_URL_RE = re.compile(
    r"""url\(\s*(['"]?)(/(?!/)[^'")]*)\1\s*\)""",
    re.IGNORECASE,
)


def stage_source(cache_dir: Path, site_root: Path, source_name: str) -> tuple[int, int]:
    """Copy ``cache_dir`` into ``site_root/static/sources/<source_name>/``,
    rewriting root-relative URLs in HTML and CSS to live under the source's
    iframe path.

    Returns ``(html_pages, total_files)``.
    """
    dest_root = site_root / "static" / "sources" / source_name
    if dest_root.exists():
        shutil.rmtree(dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)

    html_pages = 0
    total_files = 0
    prefix = f"/sources/{source_name}"
    for src in cache_dir.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(cache_dir)
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        suffix = src.suffix.lower()
        if suffix in {".html", ".htm"}:
            try:
                text = src.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(src, dest)
                total_files += 1
                continue
            text = _rewrite_attrs(text, prefix)
            text = _rewrite_css_urls(text, prefix)
            dest.write_text(text, encoding="utf-8")
            html_pages += 1
            total_files += 1
        elif suffix == ".css":
            try:
                text = src.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copy2(src, dest)
                total_files += 1
                continue
            text = _rewrite_css_urls(text, prefix)
            dest.write_text(text, encoding="utf-8")
            total_files += 1
        else:
            shutil.copy2(src, dest)
            total_files += 1

    console.log(
        f"[bold green]staged[/bold green] {html_pages} pages + "
        f"{total_files - html_pages} assets -> {dest_root}"
    )
    return html_pages, total_files


def _rewrite_attrs(text: str, prefix: str) -> str:
    def repl(m: re.Match[str]) -> str:
        attr = m.group(1)
        quote = m.group(2)
        path = m.group(3)
        return f" {attr}={quote}{prefix}{path}{quote}"
    return _URL_ATTR_RE.sub(repl, text)


def _rewrite_css_urls(text: str, prefix: str) -> str:
    def repl(m: re.Match[str]) -> str:
        quote = m.group(1)
        path = m.group(2)
        return f"url({quote}{prefix}{path}{quote})"
    return _CSS_URL_RE.sub(repl, text)
