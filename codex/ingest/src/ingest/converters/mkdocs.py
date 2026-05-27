"""
MkDocs Material HTML → Docusaurus MDX converter.

Operates on rendered HTML pulled by the wget fetcher, not on raw markdown.
MkDocs Material wraps page content in ``<article class="md-content__inner
md-typeset">`` with predictable structures for admonitions, code blocks, and
internal links.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from markdownify import MarkdownConverter
from rich.console import Console

from .common import (
    defuse_autolinks,
    extract_first_paragraph,
    generate_frontmatter,
    normalize_admonition,
    rewrite_asset_url,
    rewrite_internal_link,
)

console = Console()

# Map MkDocs Material admonition flavors → Docusaurus admonition types.
ADMONITION_MAP = {
    "note": "note",
    "info": "info",
    "tip": "tip",
    "abstract": "note",
    "summary": "note",
    "success": "tip",
    "question": "info",
    "warning": "warning",
    "caution": "warning",
    "failure": "danger",
    "danger": "danger",
    "bug": "danger",
    "example": "tip",
    "quote": "note",
    "deprecated": "warning",
}


@dataclass
class ConvertedPage:
    title: str
    description: str
    body: str
    sidebar_position: int | None = None

    def render(self) -> str:
        fm = generate_frontmatter(
            title=self.title,
            sidebar_position=self.sidebar_position,
            description=self.description or None,
        )
        return f"{fm}\n{self.body.strip()}\n"


@dataclass
class NavInfo:
    """Where an item sits in the upstream site's navigation."""
    position: int
    label: str


class MkDocsConverter(MarkdownConverter):
    """markdownify subclass with MkDocs Material aware handlers."""

    class Options(MarkdownConverter.DefaultOptions):
        heading_style = "ATX"
        code_language_callback = None  # set per-instance below
        bullets = "-"

    def __init__(self, source_name: str, **opts):
        super().__init__(**opts)
        self.source_name = source_name
        self.options["code_language_callback"] = self._detect_lang

    # --- custom tag handlers --------------------------------------------------

    def convert_div(self, el, text, parent_tags):  # type: ignore[override]
        classes = el.get("class") or []
        if "admonition" in classes:
            return self._render_admonition(el, text)
        return text

    def convert_a(self, el, text, parent_tags):  # type: ignore[override]
        href = el.get("href")
        if href:
            el["href"] = rewrite_internal_link(href, self.source_name)
        return super().convert_a(el, text, parent_tags)

    def convert_img(self, el, text, parent_tags):  # type: ignore[override]
        # Strip srcset (Docusaurus would otherwise emit broken responsive variants).
        if el.has_attr("srcset"):
            del el["srcset"]
        src = el.get("src")
        if src:
            el["src"] = rewrite_asset_url(src, self.source_name)
        return super().convert_img(el, text, parent_tags)

    # --- helpers --------------------------------------------------------------

    def _render_admonition(self, el: Tag, fallback_text: str) -> str:
        classes = el.get("class") or []
        adm_type = next(
            (ADMONITION_MAP[c] for c in classes if c in ADMONITION_MAP),
            "note",
        )
        title_el = el.find(class_="admonition-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if title_el:
            title_el.decompose()

        # Re-convert the now-title-less element's children to markdown.
        inner_text = "".join(
            self.process_tag(c, parent_tags={"_inline"} if False else set())
            if isinstance(c, Tag)
            else (c.string or "")
            for c in el.children
        )
        # process_tag returns markdown text; collapse multiple blank lines
        inner_text = re.sub(r"\n{3,}", "\n\n", inner_text).strip() or fallback_text.strip()
        return normalize_admonition(adm_type, title, inner_text)

    def _detect_lang(self, el: Tag) -> str:
        """Return the language hint for a <pre>/<code> block."""
        # markdownify hands us the <code> element; check its + parent's classes.
        candidates = list(el.get("class") or [])
        if el.parent is not None:
            candidates += list(el.parent.get("class") or [])
        for c in candidates:
            if c.startswith("language-"):
                return c.removeprefix("language-")
            if c.startswith("highlight-"):
                return c.removeprefix("highlight-")
        return ""


# --- public API ---------------------------------------------------------------


def convert_page(html: str, *, source_name: str) -> ConvertedPage | None:
    """Convert a single MkDocs Material HTML page into MDX content.

    Returns None if no main article could be located (e.g. 404 pages, search
    indexes, redirect stubs).
    """
    soup = BeautifulSoup(html, "html.parser")
    article = (
        soup.find("article", class_="md-content__inner")
        or soup.find(attrs={"role": "main"})
        or soup.find("main")
    )
    if article is None or not isinstance(article, Tag):
        return None

    # Strip Material chrome that sometimes lives inside the article.
    for sel in [
        ".md-source-file",
        ".md-content__button",
        ".md-feedback",
        ".headerlink",
        ".md-typeset__scrollwrap",
    ]:
        for node in article.select(sel):
            node.decompose()

    # Flatten inline-formatting tags inside <pre>/<code>. MkDocs Material's
    # "termynal" terminal-output snippets wrap text in <font>, <span style=>,
    # <u>, <b> etc. to colorize the terminal — markdownify would otherwise
    # leak those tags as literal HTML inside the converted code block.
    for code_block in article.find_all(["pre", "code"]):
        for inline in code_block.find_all(
            ["font", "span", "u", "b", "i", "em", "strong", "mark", "small"]
        ):
            inline.unwrap()

    # `.termy` blocks (FastAPI's pseudo-terminal animations) embed escaped HTML
    # like `&lt;font color=...&gt;` that MkDocs Material's runtime reinterprets
    # as live formatting. We can't replicate that in a static code block, so
    # double-parse the visible text to strip the markup and keep just the
    # rendered terminal text.
    for termy in article.find_all("div", class_="termy"):
        visible = termy.get_text()
        plain = BeautifulSoup(visible, "html.parser").get_text()
        plain = plain.strip("\n")
        new_pre = soup.new_tag("pre")
        new_code = soup.new_tag("code")
        new_code["class"] = ["language-console"]
        new_code.string = plain
        new_pre.append(new_code)
        termy.replace_with(new_pre)

    h1 = article.find("h1")
    title = h1.get_text(strip=True) if h1 else _fallback_title(soup)
    if h1:
        # Avoid duplicating the title — frontmatter renders it.
        h1.decompose()

    converter = MkDocsConverter(source_name=source_name)
    body = converter.convert_soup(article)
    body = _postprocess_markdown(body)

    description = extract_first_paragraph(body)
    return ConvertedPage(title=title, description=description, body=body)


def _fallback_title(soup: BeautifulSoup) -> str:
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text(strip=True)
        # MkDocs often suffixes "- Project Name"; trim it.
        text = re.split(r"\s+[-–|]\s+", text)[0]
        return text
    return "Untitled"


def _postprocess_markdown(text: str) -> str:
    """Clean up markdownify output and defuse MDX hazards."""
    text = defuse_autolinks(text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


# --- tree conversion ---------------------------------------------------------


def parse_nav_order(cache_dir: Path) -> dict[str, NavInfo]:
    """Walk MkDocs Material's primary navigation on a cached page to extract a
    flat mapping ``url_path → NavInfo(position, label)``.

    The site's home page carries the global nav; we fall back to any
    ``index.html`` if the root isn't cached. Items appear in document order,
    which preserves the hierarchical ordering across nested sections.
    """
    home = cache_dir / "index.html"
    if not home.exists():
        home = next(cache_dir.rglob("index.html"), None)
        if home is None:
            return {}

    try:
        html = home.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    nav = soup.select_one("nav.md-nav.md-nav--primary")
    if nav is None:
        return {}

    out: dict[str, NavInfo] = {}
    counter = 0
    for a in nav.find_all("a", class_="md-nav__link"):
        href = a.get("href", "")
        if not href or href.startswith(("#", "http://", "https://", "mailto:")):
            continue
        url_path = urlparse(urljoin("/", href)).path
        if "." not in Path(url_path).name and not url_path.endswith("/"):
            url_path += "/"
        if url_path in out:
            continue
        label = a.get_text(strip=True)
        counter += 1
        out[url_path] = NavInfo(position=counter, label=label or url_path)
    return out


def convert_tree(
    cache_dir: Path,
    output_dir: Path,
    *,
    source_name: str,
) -> tuple[int, dict[str, NavInfo]]:
    """Walk ``cache_dir`` and emit MDX files into ``output_dir``.

    Mirrors the URL structure but flattens leaf pages: a URL ``/foo/`` whose
    directory has no sub-pages becomes ``foo.mdx``; one with sub-pages keeps
    ``foo/index.mdx`` as its category landing page. The root URL becomes
    ``index.mdx``.

    Returns ``(count, nav_order)`` so callers (the emitter) can use the parsed
    upstream nav order to position category folders.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    html_files = sorted(cache_dir.rglob("*.html"))
    nav_order = parse_nav_order(cache_dir)

    # A directory is a "category" if it contains nested subdirs that themselves
    # contain index.html. Leaf directories (only their own index.html) get
    # flattened.
    categories: set[Path] = set()
    for html in html_files:
        if html.name != "index.html":
            continue
        for child in html.parent.iterdir():
            if child.is_dir() and (child / "index.html").exists():
                categories.add(html.parent.relative_to(cache_dir))
                break

    count = 0
    for html_path in html_files:
        rel = html_path.relative_to(cache_dir)
        mdx_rel = _map_output_path(rel, categories)
        url_path = _url_for_rel(rel)

        try:
            html = html_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            console.log(f"[yellow]skip[/yellow] {rel} (binary)")
            continue

        page = convert_page(html, source_name=source_name)
        if page is None:
            console.log(f"[yellow]skip[/yellow] {rel} (no main content)")
            continue

        info = nav_order.get(url_path)
        if info is not None:
            page.sidebar_position = info.position

        out_path = output_dir / mdx_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(page.render(), encoding="utf-8")
        count += 1

    console.log(f"[bold green]converted {count} pages[/bold green] for {source_name}")
    return count, nav_order


def _url_for_rel(rel: Path) -> str:
    """Convert a cached file path back into its source URL path.

    ``tutorial/first-steps/index.html`` → ``/tutorial/first-steps/``
    ``index.html`` → ``/``
    """
    if rel.name == "index.html":
        parts = rel.parent.parts
    else:
        parts = rel.with_suffix("").parts
    if not parts or parts == (".",):
        return "/"
    return "/" + "/".join(parts) + "/"


def _map_output_path(rel: Path, categories: set[Path]) -> Path:
    """Decide the MDX path for a cached HTML file.

    See ``convert_tree`` docstring for the rules.
    """
    if rel.name != "index.html":
        return rel.with_suffix(".mdx")

    parent = rel.parent
    if parent == Path("."):
        # Root index page.
        return Path("index.mdx")
    if parent in categories:
        # Category with children — keep as <parent>/index.mdx.
        return parent / "index.mdx"
    # Leaf page — flatten to <parent>.mdx alongside its siblings.
    return parent.with_suffix(".mdx")
