"""Emit per-source metadata.

After the pivot to native HTML + iframe rendering, the only sidekick file
needed is ``_manifest.json`` — Docusaurus no longer reads any of the
ingested content directly, so the previous ``_category_.json`` work is
gone.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

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
