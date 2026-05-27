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
    r"""<link[^>]*\brel=["'][^"']*\b(?:icon|apple-touch-icon)\b[^"']*["'][^>]*>""",
    re.IGNORECASE,
)
_HREF_RE = re.compile(r"""\bhref=["']([^"']+)["']""", re.IGNORECASE)
_SIZES_RE = re.compile(r"""\bsizes=["']?(\d+)x(\d+)""", re.IGNORECASE)

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
      1. SVG (resolution-independent)
      2. ``rel="apple-touch-icon"`` (usually 180x180)
      3. The largest ``sizes="WxH"`` PNG
      4. The first plain icon link as a fallback
    """
    candidates = [output_dir / "index.html", output_dir / "overview.html"]
    for html_file in candidates:
        if not html_file.exists():
            continue
        try:
            head = html_file.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            continue

        scored: list[tuple[int, str]] = []  # (score, href)
        for link_tag in _ICON_LINK_RE.findall(head):
            href_match = _HREF_RE.search(link_tag)
            if not href_match:
                continue
            href = href_match.group(1).strip()
            if not href or href.startswith("data:"):
                continue

            score = _favicon_score(link_tag, href)
            scored.append((score, href))

        if scored:
            scored.sort(key=lambda s: s[0], reverse=True)
            best = scored[0][1]
            if best.startswith("/"):
                return best
            return f"/sources/{source_name}/{best.lstrip('./')}"
    return None


def _favicon_score(link_tag: str, href: str) -> int:
    if href.lower().endswith(".svg"):
        return 10_000
    if "apple-touch-icon" in link_tag.lower():
        return 5_000
    size_match = _SIZES_RE.search(link_tag)
    if size_match:
        return int(size_match.group(1))  # width as score (sizes="32x32" → 32)
    return 1


def write_manifest(output_dir: Path, source: Source, page_count: int) -> Path:
    """Write ``<output_dir>/_manifest.json`` for one source."""
    manifest = {
        "name": _display_name(source),
        "dir": source.name,
        "tag": source.tag,
        "color": source.color,
        "version": source.version,
        "page_count": page_count,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_url": source.url,
        "favicon": _detect_favicon(output_dir, source.name),
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
