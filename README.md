# Codex — Offline Documentation Viewer

A locally-hosted library that aggregates documentation from multiple Python/JS
packages into a single interface. Each source's native HTML build (MkDocs,
Sphinx, etc.) is fetched once, staged into a static directory, and served
inside an iframe by a thin Docusaurus shell. The result is a fully offline,
browser-readable docs library with the upstream styling preserved.

## Bundled documentation

| Package | Version | Pages | Upstream |
| --- | --- | --- | --- |
| Envrax | 0.3.1 | 33 | <https://envrax.achronus.dev/> |
| FastAPI | 0.115 | 151 | <https://fastapi.tiangolo.com/> |
| Flax | 0.10.4 | 141 | <https://flax.readthedocs.io/en/latest/> |
| JAX | 0.6.1 | 1,699 | <https://docs.jax.dev/en/latest/> |
| MkDocs Material | 9.6 | 108 | <https://squidfunk.github.io/mkdocs-material/> |
| MuJoCo | 3.3.0 | 66 | <https://mujoco.readthedocs.io/en/stable/> |
| Mujorax | 0.2.0 | 39 | <https://mujorax.achronus.dev/> |
| Next.js | 15.2 | 453 | <https://nextjs.org/docs> |
| Optax | 0.2.5 | 40 | <https://optax.readthedocs.io/en/latest/> |
| Orbax | 0.1.9 | 154 | <https://orbax.readthedocs.io/en/latest/> |
| React | 19.1 | 158 | <https://react.dev/> |
| Tailwind CSS | 4.1 | 227 | <https://tailwindcss.com/> |

To add or remove sources, edit `codex/codex.yaml` and re-run `ingest sync`.

## Running locally

The staged docs live inside the repo (`codex/site/static/sources/`), so a
clean clone already contains everything needed to browse.

```bash
git clone <this-repo>
cd offline-docs/codex/site
npm install
npm run start
```

Visit `http://localhost:3000`. The landing page lists every staged source as a
tile; click one to load its docs in the iframe. The collapsible left sidebar
lets you switch between sources at any time. URLs with a `#<source>` hash deep
link directly to a specific package.

### Production build

```bash
cd codex/site
npm run build
npm run serve        # serves the build/ directory locally
```

The `build/` directory is fully self-contained and can be hosted on any static
file server.

## Refreshing the docs

The `ingest` CLI fetches each source's native HTML build and stages it under
`codex/site/static/sources/<name>/`. End-users don't need it — staged output is
committed to the repo. Run it when you want to pick up upstream changes or add
a new source.

**Prerequisites**: Python ≥ 3.13 with [`uv`](https://docs.astral.sh/uv/).

```bash
cd codex/ingest
uv venv
.venv/Scripts/activate            # PowerShell: .venv\Scripts\Activate.ps1
uv pip install -e ".[local,spa]"  # both optional extras (see below)
playwright install chromium       # only needed for `spa` sources

# Fetch + stage everything
ingest sync

# Or a subset
ingest sync --only fastapi,flax
```

### Optional extras

- **`[local]`** adds `mkdocs` + `mkdocs-material` so the local fetcher can
  build `mkdocs-local` sources (e.g. Envrax/Mujorax). Each project's MkDocs
  plugins must also be installed in this venv —
  `uv pip install "mkdocstrings[python]"`, for example.
- **`[spa]`** adds Playwright so the SPA fetcher can render JS-heavy sites
  (React, Next.js). After installing, run `playwright install chromium` once
  to fetch the headless browser binary.

For any `mkdocs-local` entries in `codex/codex.yaml` (e.g. Envrax/Mujorax),
clone the project repo into `codex/sources/<name>/` first. SPA sources don't
need anything on disk — Chromium fetches the live site.

### Ingest CLI commands

```bash
ingest sync                       # fetch + stage everything
ingest sync --only <names>        # comma-separated subset
ingest fetch --only <name>        # just download into the cache
ingest stage --only <name>        # cache → static/sources/<name>/
ingest list                       # show every source + cached/staged status
ingest clean --only <name>        # drop a source's cached download
ingest catalogue                  # rewrite static/sources/_catalogue.json
ingest manifest                   # refresh per-source manifests (and catalogue)
```

The catalogue is regenerated automatically after every successful stage.

## Project layout

```text
codex/
├── codex.yaml          # Source catalogue (user-editable)
├── ingest/             # Python CLI — fetches + stages sources (maintainer-only)
│   └── src/ingest/
│       ├── cli.py
│       ├── stager.py
│       └── fetchers/   # wget, local mkdocs, playwright SPA
├── site/               # Docusaurus shell (iframe + library sidebar)
│   ├── src/
│   │   ├── pages/index.tsx
│   │   ├── components/{Landing,LibrarySidebar}/
│   │   └── data/manifests.ts
│   └── static/sources/ # Native HTML for each source (committed)
└── sources/            # User-supplied local project repos (gitignored)
```
