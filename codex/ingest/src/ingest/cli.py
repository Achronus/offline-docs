"""Codex ingest CLI."""
from __future__ import annotations

import shutil
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import CodexConfig, Source, cache_root, find_config, load
from .emitter import write_catalogue, write_manifest
from .fetchers import local as local_fetcher
from .fetchers import rtd as rtd_fetcher
from .fetchers import wget as wget_fetcher
from .stager import stage_source

console = Console()


def _load() -> CodexConfig:
    return load(find_config())


def _selected(cfg: CodexConfig, only: tuple[str, ...]) -> list[Source]:
    if not only:
        return list(cfg.sources.values())
    # Accept both `--only a --only b` and `--only a,b`.
    names: list[str] = []
    for raw in only:
        names.extend(n.strip() for n in raw.split(",") if n.strip())
    out: list[Source] = []
    for name in names:
        if name not in cfg.sources:
            raise click.ClickException(f"Unknown source: {name}")
        out.append(cfg.sources[name])
    return out


@click.group()
@click.version_option(__version__, prog_name="ingest")
def main() -> None:
    """Fetch documentation sources and stage them for offline reading."""


@main.command(name="list")
def list_sources() -> None:
    """Show all sources defined in codex.yaml and their cached/staged status."""
    cfg = _load()
    table = Table(title="Codex sources")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Version")
    table.add_column("Cached?")
    table.add_column("Staged?")
    for src in cfg.sources.values():
        cached = (cache_root() / src.name).exists()
        staged = (cfg.sources_dir / src.name / "_manifest.json").exists()
        table.add_row(
            src.name,
            src.type,
            src.version or "—",
            "yes" if cached else "no",
            "yes" if staged else "no",
        )
    console.print(table)


@main.command()
@click.option("--only", multiple=True, help="Restrict to specific sources.")
def fetch(only: tuple[str, ...]) -> None:
    """Download source HTML + assets into the cache."""
    cfg = _load()
    for src in _selected(cfg, only):
        _do_fetch(src)


@main.command()
def catalogue() -> None:
    """Regenerate static/sources/_catalogue.json from currently-staged sources.

    The catalogue is written automatically after every `stage`/`sync`, but
    you can rerun this command directly if you've removed a source or
    edited codex.yaml's order.
    """
    cfg = _load()
    path = write_catalogue(cfg.sources_dir, list(cfg.sources.keys()))
    console.print(f"[green]wrote[/green] {path}")


@main.command()
@click.option("--only", multiple=True, help="Restrict to specific sources.")
def stage(only: tuple[str, ...]) -> None:
    """Stage cached content into the site's static tree (URL-rewritten)."""
    cfg = _load()
    for src in _selected(cfg, only):
        _do_stage(src, cfg)


@main.command()
@click.option("--only", multiple=True, help="Restrict to specific sources.")
def sync(only: tuple[str, ...]) -> None:
    """Fetch + stage in one step."""
    cfg = _load()
    for src in _selected(cfg, only):
        _do_fetch(src)
        _do_stage(src, cfg)


@main.command()
@click.option("--only", multiple=True, help="Restrict to specific sources.")
@click.confirmation_option(prompt="Remove cached downloads?")
def clean(only: tuple[str, ...]) -> None:
    """Remove cached downloads."""
    cfg = _load()
    for src in _selected(cfg, only):
        cache_dir = cache_root() / src.name
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            console.print(f"[green]removed[/green] {cache_dir}")
        else:
            console.print(f"[dim]nothing to remove for {src.name}[/dim]")


# --- workers ------------------------------------------------------------------


def _do_fetch(src: Source) -> Path:
    cache_dir = cache_root() / src.name
    console.rule(f"[bold]fetch[/bold] {src.name} ({src.type})")

    if src.type in ("mkdocs", "docusaurus", "sphinx-html"):
        if not src.url:
            raise click.ClickException(f"{src.name}: 'url' is required")
        return wget_fetcher.fetch(
            src.url, cache_dir, exclude_pattern=src.exclude_pattern
        )

    if src.type == "mkdocs-local":
        if not src.repo_path:
            raise click.ClickException(
                f"{src.name}: 'repo_path' is required for mkdocs-local sources. "
                f"Set it in codex.yaml (e.g. ./sources/{src.name})."
            )
        return local_fetcher.fetch(Path(src.repo_path), cache_dir)

    if src.type == "spa":
        raise click.ClickException(
            f"{src.name}: spa fetcher not implemented yet (Phase 5)"
        )

    raise click.ClickException(f"{src.name}: unknown type {src.type!r}")


def _do_stage(src: Source, cfg: CodexConfig) -> None:
    cache_dir = cache_root() / src.name
    if not cache_dir.exists():
        raise click.ClickException(
            f"{src.name}: cache not found at {cache_dir}. "
            f"Run `ingest fetch --only {src.name}` first."
        )

    dest_dir = cfg.sources_dir / src.name
    console.rule(f"[bold]stage[/bold] {src.name} -> {dest_dir}")

    pages, files = stage_source(cache_dir, cfg.site_root, src.name)
    write_manifest(dest_dir, src, pages)
    write_catalogue(cfg.sources_dir, list(cfg.sources.keys()))
    console.print(
        f"[bold green]done[/bold green]: {pages} pages ({files} files total) "
        f"in {dest_dir}"
    )


if __name__ == "__main__":
    main()
