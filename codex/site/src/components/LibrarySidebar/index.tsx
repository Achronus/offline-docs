import React from 'react';
import {useLocation, useHistory} from '@docusaurus/router';
import {manifests, type Manifest} from '@site/src/data/manifests';

export default function LibrarySidebar(): React.ReactElement {
  const location = useLocation();
  const history = useHistory();

  const active = manifests.find((m) =>
    location.pathname === `/${m.dir}` ||
    location.pathname.startsWith(`/${m.dir}/`),
  );

  return (
    <aside className="codex-library-sidebar">
      <div className="codex-logo">
        <span>Codex</span>
        <span className="codex-offline-badge">offline</span>
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
            className={m.dir === active?.dir ? 'active' : ''}
            onClick={() => history.push(`/${m.dir}/`)}
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
