"""Shared helpers used by every converter."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

# MDX reserves these characters in JSX contexts. Inside text content they
# usually round-trip cleanly, but in frontmatter they must be escaped.
_FRONTMATTER_QUOTE_RE = re.compile(r'(["\\])')


def slugify_heading(text: str) -> str:
    """Docusaurus-compatible anchor slug. Lowercase, hyphens, alnum only."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.strip("-")


def normalize_admonition(adm_type: str, title: str, body: str) -> str:
    """Render a Docusaurus admonition block.

    Output:
        :::type[Title]
        body
        :::
    """
    body = body.strip()
    if title:
        # Escape brackets in title to keep MDX happy
        safe_title = title.replace("[", "\\[").replace("]", "\\]")
        header = f":::{adm_type}[{safe_title}]"
    else:
        header = f":::{adm_type}"
    return f"\n{header}\n\n{body}\n\n:::\n"


def rewrite_asset_url(href: str, source_name: str) -> str:
    """Rewrite an asset URL (``<img src>`` etc.) to live under
    ``/img/<source>/`` in the site's static tree.

    Absolute external URLs and data URIs pass through unchanged. Site-relative
    paths are prefixed with ``/img/<source>`` so they resolve against the
    files copied by ``copy_cached_assets``.
    """
    if not href:
        return href
    if href.startswith(("http://", "https://", "data:", "//", "mailto:", "tel:")):
        return href
    if href.startswith("/"):
        return f"/img/{source_name}{href}"
    return href


_DRAWIO_SVG_ATTR_RE = re.compile(r'\s(?:host|content)="[^"]*"')


def _clean_drawio_svg(content: str) -> str:
    """Strip drawio editor metadata (``host=`` and ``content=``) from the
    opening ``<svg>`` tag.

    drawio's ``content`` attribute carries the entire serialized diagram —
    often tens of KB. image-size 2.x only scans the first 1000 bytes for the
    closing ``>`` of the ``<svg>`` tag, so bloated opening tags make it
    incorrectly reject otherwise-valid SVGs. The visible rendering uses the
    SVG paths/groups inside the file; the stripped attributes are only used
    when round-tripping back to the drawio editor.
    """
    close = content.find(">")
    if close == -1:
        return content
    opening = content[: close + 1]
    if "host=" not in opening and "content=" not in opening:
        return content
    return _DRAWIO_SVG_ATTR_RE.sub("", opening) + content[close + 1 :]


def copy_cached_assets(cache_dir: Path, site_root: Path, source_name: str) -> int:
    """Copy non-HTML files from ``cache_dir`` into the site's static tree.

    Each file ``cache_dir/<rel>`` is copied to
    ``site_root/static/img/<source_name>/<rel>`` so the URLs produced by
    ``rewrite_asset_url`` resolve. SVGs get a small cleanup pass to strip
    drawio editor metadata that confuses Docusaurus's image-size probe.
    Returns the number of files copied (skips already-present same-size files).
    """
    dest_root = site_root / "static" / "img" / source_name
    count = 0
    for src in cache_dir.rglob("*"):
        if not src.is_file():
            continue
        if src.suffix.lower() == ".html":
            continue
        rel = src.relative_to(cache_dir)
        dest = dest_root / rel
        if src.suffix.lower() == ".svg":
            try:
                text = src.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Non-UTF-8 SVG — copy as-is.
                if dest.exists() and dest.stat().st_size == src.stat().st_size:
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                count += 1
                continue
            cleaned = _clean_drawio_svg(text)
            if dest.exists() and dest.stat().st_size == len(cleaned.encode("utf-8")):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(cleaned, encoding="utf-8")
            count += 1
            continue
        if dest.exists() and dest.stat().st_size == src.stat().st_size:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        count += 1
    return count


def rewrite_internal_link(href: str, source_name: str) -> str:
    """Rewrite a fetched-site link into a Docusaurus-friendly relative path.

    - Absolute external URLs pass through.
    - Internal links lose `.html` / `index.html` extensions.
    - Fragments are preserved.
    """
    if not href:
        return href
    if href.startswith(("http://", "https://", "mailto:", "tel:", "//", "#")):
        return href

    # Split off fragment + query
    fragment = ""
    query = ""
    if "#" in href:
        href, fragment = href.split("#", 1)
        fragment = "#" + fragment
    if "?" in href:
        href, query = href.split("?", 1)
        query = "?" + query

    # Strip trailing index.html / .html
    if href.endswith("/index.html"):
        href = href[: -len("/index.html")] + "/"
    elif href.endswith("index.html"):
        href = href[: -len("index.html")]
    elif href.endswith(".html"):
        href = href[: -len(".html")]

    return href + query + fragment


def generate_frontmatter(
    *,
    title: str,
    sidebar_position: int | None = None,
    description: str | None = None,
    extra: dict[str, str] | None = None,
) -> str:
    """Return a YAML frontmatter block (including delimiters) for an MDX file."""
    lines = ["---"]
    if title:
        lines.append(f'title: "{_yaml_quote(title)}"')
    if sidebar_position is not None:
        lines.append(f"sidebar_position: {sidebar_position}")
    if description:
        lines.append(f'description: "{_yaml_quote(description)}"')
    if extra:
        for k, v in extra.items():
            lines.append(f'{k}: "{_yaml_quote(str(v))}"')
    lines.append("---\n")
    return "\n".join(lines)


def _yaml_quote(text: str) -> str:
    text = text.replace("\n", " ").strip()
    return _FRONTMATTER_QUOTE_RE.sub(r"\\\1", text)


def copy_asset(src: Path, dest_base: Path, source_name: str) -> str:
    """Copy an asset into the site's static/img/<source>/ tree.

    ``dest_base`` should be the site root (so that ``dest_base/static/img/<source>``
    is the final asset directory). Returns the absolute web path
    ``/img/<source>/<filename>``.
    """
    dest_dir = dest_base / "static" / "img" / source_name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if not dest.exists():
        shutil.copy2(src, dest)
    return f"/img/{source_name}/{src.name}"


# Markdown autolinks (<https://...>, <mailto:foo>, <foo@bar>) are valid CommonMark
# but trip MDX 3's JSX parser ("Unexpected character `/`…"). Convert to explicit
# link syntax before emission.
_URL_AUTOLINK_RE = re.compile(r"<((?:https?|ftp|mailto):[^>\s]+)>")
_EMAIL_AUTOLINK_RE = re.compile(r"<([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})>")


def defuse_autolinks(markdown: str) -> str:
    """Rewrite ``<url>`` and ``<foo@bar>`` autolinks to ``[url](url)`` form."""
    markdown = _URL_AUTOLINK_RE.sub(lambda m: f"[{m.group(1)}]({m.group(1)})", markdown)
    markdown = _EMAIL_AUTOLINK_RE.sub(
        lambda m: f"[{m.group(1)}](mailto:{m.group(1)})", markdown
    )
    return markdown


def extract_first_paragraph(text: str, max_chars: int = 160) -> str:
    """Pull the first non-empty paragraph from converted markdown.

    Used to seed the frontmatter ``description``.
    """
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith(("#", "```", ":::", "|", "<", "import ")):
            continue
        # Strip markdown link syntax for cleaner description
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", block)
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) > max_chars:
            cleaned = cleaned[: max_chars - 1].rstrip() + "…"
        return cleaned
    return ""
