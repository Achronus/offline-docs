"""Emit per-source metadata.

After the pivot to native HTML + iframe rendering, the only sidekick file
needed is ``_manifest.json`` — Docusaurus no longer reads any of the
ingested content directly, so the previous ``_category_.json`` work is
gone.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import Source

_ICON_LINK_RE = re.compile(
    r"""<link\b[^>]*>""",
    re.IGNORECASE,
)
# Match attribute values whether they're double-quoted, single-quoted, or
# unquoted (MkDocs Material's HTML minifier strips the quotes).
# Unquoted values per HTML5 may contain slashes (they're part of URLs) — only
# whitespace and ``>`` end the token.
_REL_RE = re.compile(
    r"""\brel\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
    re.IGNORECASE,
)
_HREF_RE = re.compile(
    r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""",
    re.IGNORECASE,
)
_SIZES_RE = re.compile(
    r"""\bsizes\s*=\s*["']?(\d+)x(\d+)""",
    re.IGNORECASE,
)


def _first_group(m: re.Match[str] | None) -> str | None:
    """Return the first non-empty capture group from a multi-alternative regex."""
    if not m:
        return None
    for group in m.groups():
        if group:
            return group
    return None
_META_REFRESH_RE = re.compile(
    r"""<meta[^>]*http-equiv=["']refresh["'][^>]*content=["'][^"']*url\s*=\s*([^"';\s]+)""",
    re.IGNORECASE,
)

# Display name overrides for sources whose canonical name isn't a simple
# title-case of the slug (acronyms, mixed case, punctuation).
DISPLAY_NAMES: dict[str, str] = {
    "fastapi": "FastAPI",
    "jax": "JAX",
    "flax": "Flax",
    "optax": "Optax",
    "orbax": "Orbax",
    "mujoco": "MuJoCo",
    "mkdocs-material": "MkDocs Material",
    "envrax": "Envrax",
    "mujorax": "Mujorax",
    "nextjs": "Next.js",
    "react": "React",
    "docusaurus": "Docusaurus",
}


def _detect_favicon(output_dir: Path, source_name: str) -> str | None:
    """Find the best-quality favicon by parsing icon ``<link>`` tags in
    the source's landing page.

    Prefers, in order:
      1. ``rel="apple-touch-icon"`` (usually 180x180, full-colour)
      2. The largest ``sizes="WxH"`` raster icon
      3. SVG icons (resolution-independent, but watch out for monochrome
         ``rel="mask-icon"`` which we skip entirely)
      4. The first plain icon link as a fallback

    If the source's ``index.html`` is a meta-refresh stub (the case for
    SPAs we wrote a redirect for), we follow it and look there too.
    """
    seen: set[Path] = set()

    def scan(html_file: Path, depth: int = 0) -> str | None:
        if depth > 2 or not html_file.exists() or html_file in seen:
            return None
        seen.add(html_file)
        try:
            head = html_file.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            return None

        scored: list[tuple[int, str]] = []
        for link_tag in _ICON_LINK_RE.findall(head):
            rel_val = _first_group(_REL_RE.search(link_tag))
            if not rel_val:
                continue
            rels = rel_val.lower().split()
            if not any(r in ("icon", "apple-touch-icon", "shortcut") for r in rels):
                continue
            # mask-icon is monochrome silhouette — skip even though it matches
            # the broader icon regex.
            if any(r == "mask-icon" for r in rels):
                continue
            href = _first_group(_HREF_RE.search(link_tag))
            if not href:
                continue
            href = href.strip()
            if not href or href.startswith("data:"):
                continue
            scored.append((_favicon_score(rels, link_tag, href), href))

        if scored:
            scored.sort(key=lambda s: s[0], reverse=True)
            best = scored[0][1]
            return best if best.startswith("/") else f"/sources/{source_name}/{best.lstrip('./')}"

        # No icon here — follow meta refresh and try again (SPA stub case).
        refresh = _META_REFRESH_RE.search(head)
        if refresh:
            target_rel = refresh.group(1).strip()
            target = (html_file.parent / target_rel).resolve()
            if target.is_dir():
                target = target / "index.html"
            elif not target.suffix:
                target = target / "index.html"
            return scan(target, depth + 1)
        return None

    for entry in (output_dir / "index.html", output_dir / "overview.html"):
        result = scan(entry)
        if result:
            return result
    return None


def _favicon_score(rels: list[str], link_tag: str, href: str) -> int:
    """Higher = better. We prefer transparent variants (regular favicons,
    SVGs) over apple-touch-icons, which are designed for iOS home-screen
    use and almost always have a solid brand-colour background. Larger
    sizes are still preferred within each tier.
    """
    is_apple = "apple-touch-icon" in rels
    if href.lower().endswith(".svg"):
        # Scalable, almost always transparent — beat any raster.
        return 100_000
    size_match = _SIZES_RE.search(link_tag)
    if size_match:
        width = int(size_match.group(1))
        return width * (5 if is_apple else 1_000)
    return 1


def write_manifest(output_dir: Path, source: Source, page_count: int) -> Path:
    """Write ``<output_dir>/_manifest.json`` for one source."""
    # codex.yaml override wins; otherwise auto-detect from the source's HTML.
    favicon = source.icon or _detect_favicon(output_dir, source.name)
    manifest = {
        "name": _display_name(source),
        "dir": source.name,
        "tag": source.tag,
        "color": source.color,
        "version": source.version,
        "page_count": page_count,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_url": source.url,
        "favicon": favicon,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def _display_name(source: Source) -> str:
    return DISPLAY_NAMES.get(source.name, source.name.replace("-", " ").title())


def write_catalogue(sources_dir: Path, ordered_names: list[str]) -> Path:
    """Scan ``sources_dir`` and emit ``_catalogue.json`` — a flat list of
    every staged source's manifest, in the order they appear in
    ``ordered_names`` (typically the codex.yaml source order).

    Sources without a ``_manifest.json`` (not yet staged) are skipped.
    """
    catalogue: list[dict] = []
    for name in ordered_names:
        manifest_path = sources_dir / name / "_manifest.json"
        if not manifest_path.exists():
            continue
        try:
            catalogue.append(json.loads(manifest_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue

    sources_dir.mkdir(parents=True, exist_ok=True)
    out = sources_dir / "_catalogue.json"
    out.write_text(json.dumps(catalogue, indent=2) + "\n", encoding="utf-8")
    return out
