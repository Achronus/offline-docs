"""Local MkDocs project fetcher.

Runs ``mkdocs build`` in a user-owned repository and copies the resulting
``site/`` directory into the cache for the standard MkDocs converter to
process. Operates identically to the wget fetcher from there on — same
``index.html`` files, same nav structure, same converter pipeline.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def fetch(repo_path: Path, cache_dir: Path) -> Path:
    """Build the MkDocs project at ``repo_path`` and stage its ``site/`` output
    into ``cache_dir``. Returns ``cache_dir`` for chaining.

    Raises ``FileNotFoundError`` if the repo or its ``mkdocs.yml`` are missing,
    and ``RuntimeError`` if the build itself fails (e.g. missing plugins).
    """
    repo_path = Path(repo_path).resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"repo_path does not exist: {repo_path}")

    mkdocs_yml = repo_path / "mkdocs.yml"
    if not mkdocs_yml.exists():
        # Some projects use .yaml extension instead.
        alt = repo_path / "mkdocs.yaml"
        if not alt.exists():
            raise FileNotFoundError(
                f"mkdocs.yml not found at {mkdocs_yml}. Is {repo_path} a "
                "MkDocs project root?"
            )

    site_dir = repo_path / "site"
    console.log(f"running [bold]mkdocs build[/bold] in {repo_path}")
    try:
        result = subprocess.run(
            ["mkdocs", "build", "--clean"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "`mkdocs` not on PATH. Install it into the ingest venv: "
            "`uv pip install -e .[local]` (adds mkdocs + mkdocs-material). "
            "Plugins required by individual repos must be installed separately."
        ) from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or e.stdout or "").strip()
        raise RuntimeError(
            f"mkdocs build failed in {repo_path}:\n{stderr}"
        ) from e

    # Surface any non-fatal mkdocs output for visibility.
    for line in (result.stderr or "").splitlines():
        if line.strip():
            console.log(f"  [dim]{line}[/dim]")

    if not site_dir.exists():
        raise RuntimeError(
            f"mkdocs build completed but {site_dir} was not produced. Check "
            "the project's `site_dir` config."
        )

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    shutil.copytree(site_dir, cache_dir)

    page_count = sum(1 for _ in cache_dir.rglob("*.html"))
    console.log(
        f"[bold green]cached {page_count} pages[/bold green] from {repo_path.name}"
    )
    return cache_dir
