"""Codex ingest CLI."""
from __future__ import annotations

import shutil
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import CodexConfig, Source, cache_root, find_config, load
from .converters import mkdocs as mkdocs_converter
from .converters.common import copy_cached_assets
from .emitter import write_categories, write_manifest
from .fetchers import local as local_fetcher
from .fetchers import wget as wget_fetcher

console = Console()


def _load() -> CodexConfig:
    return load(find_config())


def _selected(cfg: CodexConfig, only: tuple[str, ...]) -> list[Source]:
    if not only:
        return list(cfg.sources.values())
    out: list[Source] = []
    for name in only:
        if name not in cfg.sources:
            raise click.ClickException(f"Unknown source: {name}")
        out.append(cfg.sources[name])
    return out


@click.group()
@click.version_option(__version__, prog_name="ingest")
def main() -> None:
    """Fetch and convert documentation sources defined in codex.yaml."""


@main.command(name="list")
def list_sources() -> None:
    """Show all sources defined in codex.yaml and their cached status."""
    cfg = _load()
    table = Table(title="Codex sources")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Version")
    table.add_column("Cached?")
    table.add_column("Built?")
    for src in cfg.sources.values():
        cached = (cache_root() / src.name).exists()
        built = (cfg.output_dir / src.name / "_manifest.json").exists()
        table.add_row(
            src.name,
            src.type,
            src.version or "—",
            "yes" if cached else "no",
            "yes" if built else "no",
        )
    console.print(table)


@main.command()
@click.option("--only", multiple=True, help="Restrict to specific sources.")
def fetch(only: tuple[str, ...]) -> None:
    """Download source HTML into the cache."""
    cfg = _load()
    for src in _selected(cfg, only):
        _do_fetch(src)


@main.command()
@click.option("--only", multiple=True, help="Restrict to specific sources.")
def convert(only: tuple[str, ...]) -> None:
    """Convert cached HTML into MDX under output_dir."""
    cfg = _load()
    for src in _selected(cfg, only):
        _do_convert(src, cfg)


@main.command()
@click.option("--only", multiple=True, help="Restrict to specific sources.")
def sync(only: tuple[str, ...]) -> None:
    """Fetch + convert in one step."""
    cfg = _load()
    for src in _selected(cfg, only):
        _do_fetch(src)
        _do_convert(src, cfg)


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

    if src.type in ("mkdocs", "docusaurus"):
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

    if src.type == "sphinx-html":
        raise click.ClickException(
            f"{src.name}: sphinx-html fetcher not implemented yet (Phase 4)"
        )
    if src.type == "spa":
        raise click.ClickException(
            f"{src.name}: spa fetcher not implemented yet (Phase 5)"
        )

    raise click.ClickException(f"{src.name}: unknown type {src.type!r}")


def _do_convert(src: Source, cfg: CodexConfig) -> None:
    cache_dir = cache_root() / src.name
    if not cache_dir.exists():
        raise click.ClickException(
            f"{src.name}: cache not found at {cache_dir}. Run `ingest fetch --only {src.name}` first."
        )

    output_dir = cfg.output_dir / src.name
    console.rule(f"[bold]convert[/bold] {src.name} → {output_dir}")

    if output_dir.exists():
        shutil.rmtree(output_dir)

    if src.type in ("mkdocs", "docusaurus", "mkdocs-local"):
        count, nav_order = mkdocs_converter.convert_tree(
            cache_dir, output_dir, source_name=src.name
        )
    else:
        raise click.ClickException(
            f"{src.name}: converter for type {src.type!r} not implemented yet"
        )

    write_categories(output_dir, nav_order=nav_order)
    write_manifest(output_dir, src, count)

    # Copy non-HTML cache files (images, etc.) into the site's static tree so
    # MDX URLs rewritten via rewrite_asset_url actually resolve.
    site_root = cfg.output_dir.parent  # site/docs → site/
    assets = copy_cached_assets(cache_dir, site_root, src.name)
    if assets:
        console.log(f"copied {assets} assets → {site_root / 'static' / 'img' / src.name}")

    console.print(f"[bold green]done[/bold green]: {count} pages in {output_dir}")


if __name__ == "__main__":
    main()
