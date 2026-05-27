"""Emit Docusaurus sidekick files: ``_category_.json`` and ``_manifest.json``."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from .config import Source

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
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def write_categories(
    output_dir: Path,
    nav_order: Mapping[str, object] | None = None,
) -> int:
    """Drop a ``_category_.json`` next to every subdirectory of MDX files.

    If ``nav_order`` is provided (a mapping from URL path → object with
    ``position`` and ``label`` attributes, e.g. ``NavInfo``), the category's
    label and position are taken from the upstream nav. The ``link`` field is
    intentionally omitted so Docusaurus uses the directory's ``index.mdx`` as
    the category's landing page.
    """
    written = 0
    for subdir in [p for p in output_dir.rglob("*") if p.is_dir()]:
        if (subdir / "_category_.json").exists():
            continue
        if subdir == output_dir:
            continue
        rel = subdir.relative_to(output_dir)
        url_path = "/" + "/".join(rel.parts) + "/"
        info = nav_order.get(url_path) if nav_order else None
        label = getattr(info, "label", None) or _humanize(subdir.name)
        body: dict[str, object] = {"label": label}
        position = getattr(info, "position", None)
        if position is not None:
            body["position"] = position
        (subdir / "_category_.json").write_text(
            json.dumps(body, indent=2) + "\n", encoding="utf-8"
        )
        written += 1
    return written


def _display_name(source: Source) -> str:
    return DISPLAY_NAMES.get(source.name, source.name.replace("-", " ").title())


def _humanize(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()
