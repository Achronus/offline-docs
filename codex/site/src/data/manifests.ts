// Hardcoded manifests for Phase 1 — the manifests Docusaurus plugin
// (Phase 6) replaces this with build-time-generated data sourced from each
// package's docs/<source>/_manifest.json.

export type Manifest = {
  dir: string;
  name: string;
  tag: string;
  color: string;
  version: string;
  page_count: number;
  source_url?: string;
};

export const manifests: Manifest[] = [
  {
    dir: 'jax',
    name: 'JAX',
    tag: 'Jx',
    color: '#1D9E75',
    version: '0.6.1',
    page_count: 1,
    source_url: 'https://docs.jax.dev/en/latest/',
  },
  {
    dir: 'fastapi',
    name: 'FastAPI',
    tag: 'Fa',
    color: '#1D9E75',
    version: '0.115',
    page_count: 151,
    source_url: 'https://fastapi.tiangolo.com/',
  },
  {
    dir: 'envrax',
    name: 'Envrax',
    tag: 'Ev',
    color: '#854F0B',
    version: '0.3.1',
    page_count: 33,
  },
  {
    dir: 'mujorax',
    name: 'Mujorax',
    tag: 'Mr',
    color: '#854F0B',
    version: '0.2.0',
    page_count: 39,
  },
];
