from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

SourceType = Literal[
    "sphinx-html",
    "mkdocs",
    "mkdocs-local",
    "spa",
    "docusaurus",
]


@dataclass
class CrawlConfig:
    start_paths: list[str] = field(default_factory=list)
    url_pattern: str = ""
    content_selector: str = "main"


@dataclass
class Source:
    name: str
    type: SourceType
    url: str | None = None
    download_url: str | None = None
    repo_path: str | None = None
    version: str = ""
    color: str = "#888888"
    tag: str = "??"
    crawl: CrawlConfig | None = None
    exclude_pattern: str | None = None
    """Regex matched against the URL path. Matching URLs are skipped during fetch."""
    icon: str | None = None
    """Override the auto-detected favicon. Useful when upstream's icons are
    low-res or unusably styled (e.g. only an apple-touch-icon with brand bg).
    Accepts an absolute URL path (``/img/source-icons/react.svg``) or external
    URL. When set, this wins over ``_detect_favicon``."""
    custom_search: bool = False
    """When true, the stager injects ``static/codex-search.js`` into each
    page and builds ``_codex_search.json`` so the in-iframe Ctrl+K modal
    works. For sources whose native search depends on a cloud service
    (Algolia DocSearch on React/Next.js) and so is broken offline."""


@dataclass
class CodexConfig:
    site_root: Path
    sources: dict[str, Source]
    config_path: Path

    @property
    def root(self) -> Path:
        return self.config_path.parent

    @property
    def sources_dir(self) -> Path:
        """Where staged native HTML lives (one subdir per source)."""
        return self.site_root / "static" / "sources"


def load(config_path: Path) -> CodexConfig:
    config_path = config_path.resolve()
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # Accept either the new `site_root` key or the legacy `output_dir` (where
    # MDX docs used to live — treat its parent as site_root for backwards
    # compatibility with old codex.yaml files).
    if "site_root" in raw:
        site_root = (config_path.parent / raw["site_root"]).resolve()
    elif "output_dir" in raw:
        legacy = (config_path.parent / raw["output_dir"]).resolve()
        site_root = legacy.parent
    else:
        site_root = (config_path.parent / "site").resolve()

    sources_raw = raw.get("sources", {})
    sources: dict[str, Source] = {}
    for name, body in sources_raw.items():
        crawl_raw = body.get("crawl")
        crawl = (
            CrawlConfig(
                start_paths=list(crawl_raw.get("start_paths", [])),
                url_pattern=crawl_raw.get("url_pattern", ""),
                content_selector=crawl_raw.get("content_selector", "main"),
            )
            if crawl_raw
            else None
        )
        repo_path_raw = body.get("repo_path")
        repo_path: str | None = None
        if repo_path_raw:
            rp = Path(repo_path_raw)
            if not rp.is_absolute():
                rp = (config_path.parent / rp).resolve()
            repo_path = str(rp)

        sources[name] = Source(
            name=name,
            type=body["type"],
            url=body.get("url"),
            download_url=body.get("download_url"),
            repo_path=repo_path,
            version=str(body.get("version", "")),
            color=body.get("color", "#888888"),
            tag=body.get("tag", "??"),
            crawl=crawl,
            exclude_pattern=body.get("exclude_pattern"),
            icon=body.get("icon"),
            custom_search=bool(body.get("custom_search", False)),
        )

    return CodexConfig(
        site_root=site_root,
        sources=sources,
        config_path=config_path,
    )


def find_config(start: Path | None = None) -> Path:
    """Walk up from ``start`` (or cwd) looking for codex.yaml.

    At each level we also peek inside a ``codex/`` subdirectory so the CLI
    works from the repo root, not just from inside ``codex/`` itself.
    """
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        direct = candidate / "codex.yaml"
        if direct.exists():
            return direct
        nested = candidate / "codex" / "codex.yaml"
        if nested.exists():
            return nested
    raise FileNotFoundError(
        "codex.yaml not found in current directory, any parent, or a sibling "
        "codex/ folder. Run from inside the repo."
    )


def cache_root() -> Path:
    return Path.home() / ".cache" / "codex"
