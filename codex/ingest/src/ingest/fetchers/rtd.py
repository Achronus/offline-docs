"""ReadTheDocs htmlzip fetcher.

Downloads a Sphinx project's pre-built ``htmlzip`` archive from RTD (or a
custom-domain mirror like ``docs.jax.dev``), extracts the contents into the
cache directory. The resulting cache looks identical in shape to what the
wget/local fetchers produce: HTML pages + ``_static/`` assets + ``_sources/``,
which the stager can copy verbatim into ``static/sources/<name>/``.
"""
from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests
from rich.console import Console

console = Console()


def fetch(
    source_url: str,
    cache_dir: Path,
    *,
    download_url: str | None = None,
) -> Path:
    """Download an RTD htmlzip and extract it into ``cache_dir``.

    ``download_url`` is used verbatim when provided (needed for projects on
    custom domains like JAX). Otherwise the URL is constructed from
    ``source_url`` using RTD's standard download path.
    """
    if download_url is None:
        download_url = _construct_rtd_download_url(source_url)

    console.log(f"downloading [bold]{download_url}[/bold]")
    resp = requests.get(download_url, timeout=300)
    resp.raise_for_status()
    zip_bytes = resp.content
    console.log(f"  received {len(zip_bytes) // 1024} KiB")

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        members = zf.namelist()
        # RTD htmlzips typically wrap everything in a top-level dir like
        # ``flax-latest/``. Strip it so the cache matches the URL shape that
        # other fetchers produce.
        top_dirs = {m.split("/", 1)[0] for m in members if "/" in m}
        prefix = next(iter(top_dirs)) + "/" if len(top_dirs) == 1 else ""
        if prefix:
            console.log(f"  stripping wrapper directory [dim]{prefix}[/dim]")

        for member in members:
            if not member.startswith(prefix):
                continue
            rel = member[len(prefix):]
            if not rel:
                continue
            target = cache_dir / rel
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src_file, target.open("wb") as dst_file:
                    shutil.copyfileobj(src_file, dst_file)

    pages = sum(1 for _ in cache_dir.rglob("*.html"))
    console.log(f"[bold green]extracted {pages} HTML pages[/bold green]")
    return cache_dir


def _construct_rtd_download_url(source_url: str) -> str:
    """Map a docs URL like ``https://flax.readthedocs.io/en/latest/`` to
    its RTD htmlzip download URL.

    Raises ``ValueError`` if the path doesn't look like ``/<lang>/<version>/``.
    """
    parsed = urlparse(source_url)
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError(
            f"Cannot derive RTD download URL from {source_url!r}: "
            "expected path of the form /<lang>/<version>/"
        )
    lang, version = parts[0], parts[1]
    return f"{parsed.scheme}://{parsed.netloc}/_/downloads/{lang}/{version}/htmlzip/"
