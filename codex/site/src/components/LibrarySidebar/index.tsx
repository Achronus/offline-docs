import React from 'react';
import type {Manifest} from '@site/src/data/manifests';

interface Props {
  manifests: Manifest[];
  active: string | null;
  collapsed: boolean;
  onSelect: (dir: string) => void;
  onToggle: () => void;
  onHome: () => void;
}

function PackageIcon({m}: {m: Manifest}): React.ReactElement {
  if (m.favicon) {
    return <img src={m.favicon} alt="" className="codex-package-logo" aria-hidden />;
  }
  return (
    <span className="codex-package-icon" style={{background: m.color}} aria-hidden>
      {m.tag}
    </span>
  );
}

export default function LibrarySidebar({
  manifests,
  active,
  collapsed,
  onSelect,
  onToggle,
  onHome,
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
        {activeManifest && <PackageIcon m={activeManifest} />}
      </aside>
    );
  }

  return (
    <aside className="codex-library-sidebar">
      <div className="codex-logo">
        <button
          type="button"
          className="codex-home-btn"
          onClick={onHome}
          aria-label="Go to library home"
        >
          Codex
        </button>
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
      <ul className="codex-package-list">
        {manifests.map((m: Manifest) => (
          <li
            key={m.dir}
            className={m.dir === active ? 'active' : ''}
            onClick={() => onSelect(m.dir)}
          >
            <PackageIcon m={m} />
            <span className="codex-package-name">{m.name}</span>
            <span className="codex-page-count">{m.page_count}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
