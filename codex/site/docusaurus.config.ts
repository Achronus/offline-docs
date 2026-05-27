import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Codex',
  tagline: 'Offline documentation viewer',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'http://localhost',
  baseUrl: '/',

  onBrokenLinks: 'warn',
  markdown: {
    // Ingested docs are CommonMark-shaped after conversion. Parsing them as
    // strict MDX trips on naked `<` (e.g. `<0.51.0`) and `{...}` patterns
    // that appear in Python signatures FastAPI renders outside code blocks.
    // `:::admonition` syntax still works in 'md' format — it's a Docusaurus
    // remark plugin, not an MDX feature.
    format: 'md',
    hooks: {
      onBrokenMarkdownLinks: 'warn',
      // Images referenced by ingested HTML pages aren't downloaded yet —
      // the wget fetcher only saves HTML. Phase-later polish: extend the
      // fetcher to also pull <img> assets into static/img/<source>/.
      onBrokenMarkdownImages: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  // Multi-instance docs. The classic preset hosts the first source; every
  // other source is registered as its own `@docusaurus/plugin-content-docs`
  // instance below. Phase 6 will replace this hand-maintained list with a
  // generated one driven by docs/<source>/_manifest.json.
  presets: [
    [
      'classic',
      {
        docs: {
          // No explicit `id` — Docusaurus uses the 'default' instance id, which
          // theme-classic's SearchBar requires for version lookups in
          // multi-instance setups. The first source (JAX here) doubles as the
          // 'default' docs instance.
          path: 'docs/jax',
          routeBasePath: '/jax',
          sidebarPath: './sidebars.ts',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  plugins: [
    [
      '@docusaurus/plugin-content-docs',
      {
        id: 'fastapi',
        path: 'docs/fastapi',
        routeBasePath: '/fastapi',
        sidebarPath: './sidebars.ts',
      },
    ],
    [
      require.resolve('@easyops-cn/docusaurus-search-local'),
      {
        hashed: true,
        indexBlog: false,
        docsRouteBasePath: ['/jax', '/fastapi'],
      },
    ],
  ],

  // KaTeX stylesheet — bundled locally so the site works offline.
  // Math content is introduced in Phase 4 (JAX/Sphinx docs). The CSS file +
  // KaTeX fonts must be present at static/katex/ before math will render.
  // Install: `npm install katex remark-math rehype-katex` then copy
  // node_modules/katex/dist/katex.min.css and node_modules/katex/dist/fonts/
  // into static/katex/.
  stylesheets: [
    {
      href: '/katex/katex.min.css',
      type: 'text/css',
    },
  ],

  themeConfig: {
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Codex',
      logo: {
        alt: 'Codex',
        src: 'img/logo.svg',
      },
      items: [],
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
