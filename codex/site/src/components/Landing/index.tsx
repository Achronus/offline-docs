import React from 'react';
import type {Manifest} from '@site/src/data/manifests';

interface Props {
  manifests: Manifest[];
  onSelect: (dir: string) => void;
}

export default function Landing({manifests, onSelect}: Props): React.ReactElement {
  const totalPages = manifests.reduce((acc, m) => acc + (m.page_count || 0), 0);
  const lastFetchedAt = manifests
    .map((m) => m.fetched_at)
    .filter((d): d is string => Boolean(d))
    .sort()
    .at(-1);

  return (
    <section className="codex-landing">
      <header className="codex-landing-header">
        <h1>Your offline library</h1>
        <p className="codex-landing-summary">
          {manifests.length} package{manifests.length === 1 ? '' : 's'} ·{' '}
          {totalPages.toLocaleString()} pages
          {lastFetchedAt && (
            <>
              {' · '}last synced {formatRelative(lastFetchedAt)}
            </>
          )}
        </p>
      </header>
      <ul className="codex-tile-grid">
        {manifests.map((m) => (
          <li key={m.dir}>
            <button
              type="button"
              className="codex-tile"
              onClick={() => onSelect(m.dir)}
            >
              {m.favicon ? (
                <img
                  src={m.favicon}
                  alt=""
                  className="codex-tile-logo"
                  aria-hidden
                />
              ) : (
                <span
                  className="codex-tile-icon"
                  style={{background: m.color}}
                  aria-hidden
                >
                  <span className="codex-tile-tag">{m.tag}</span>
                </span>
              )}
              <span className="codex-tile-name">{m.name}</span>
              <span className="codex-tile-meta">
                <span>{m.version || '—'}</span>
                <span>{m.page_count.toLocaleString()} pages</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;
  const diffMs = Date.now() - then;
  const mins = Math.round(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hr ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`;
  const months = Math.round(days / 30);
  return `${months} month${months === 1 ? '' : 's'} ago`;
}
