import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// Codex serves each source's native HTML (mkdocs / sphinx / spa builds) from
// static/sources/<name>/ and embeds it in an iframe inside the Codex shell.
// No Docusaurus docs/blog plugins are used — the only React content lives in
// src/pages/.

const config: Config = {
  title: 'Codex',
  tagline: 'Offline documentation viewer',
  favicon: 'img/favicon.svg',

  future: {
    v4: true,
  },

  url: 'http://localhost',
  baseUrl: '/',

  onBrokenLinks: 'warn',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
      onBrokenMarkdownImages: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: false,
        blog: false,
        pages: {},
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
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
