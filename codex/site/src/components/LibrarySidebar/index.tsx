import React from 'react';
import {manifests, type Manifest} from '@site/src/data/manifests';

interface Props {
  active: string | null;
  collapsed: boolean;
  onSelect: (dir: string) => void;
  onToggle: () => void;
}

export default function LibrarySidebar({
  active,
  collapsed,
  onSelect,
  onToggle,
}: Props): React.ReactElement {
  const activeManifest = manifests.find((m) => m.dir === active);

  if (collapsed) {
    return (
      <aside
        className="codex-library-sidebar collapsed"
        onClick={onToggle}
        role="button"
        aria-label="Open library sidebar"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') onToggle();
        }}
      >
        <span className="codex-toggle" aria-hidden>
          ☰
        </span>
        {activeManifest && (
          <span
            className="codex-package-icon"
            style={{background: activeManifest.color}}
            aria-hidden
          >
            {activeManifest.tag}
          </span>
        )}
      </aside>
    );
  }

  return (
    <aside className="codex-library-sidebar">
      <div className="codex-logo">
        <span>Codex</span>
        <span className="codex-offline-badge">offline</span>
        <button
          type="button"
          className="codex-collapse-btn"
          onClick={onToggle}
          aria-label="Collapse library sidebar"
        >
          ←
        </button>
      </div>
      <input
        type="search"
        placeholder="Search all docs…"
        className="codex-search"
        aria-label="Search all docs"
      />
      <ul className="codex-package-list">
        {manifests.map((m: Manifest) => (
          <li
            key={m.dir}
            className={m.dir === active ? 'active' : ''}
            onClick={() => onSelect(m.dir)}
          >
            <span
              className="codex-package-icon"
              style={{background: m.color}}
              aria-hidden
            >
              {m.tag}
            </span>
            <span className="codex-package-name">{m.name}</span>
            <span className="codex-page-count">{m.page_count}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
