import React, {useCallback, useEffect, useState} from 'react';
import Head from '@docusaurus/Head';
import BrowserOnly from '@docusaurus/BrowserOnly';
import LibrarySidebar from '@site/src/components/LibrarySidebar';
import {manifests} from '@site/src/data/manifests';

function pickInitial(): string | null {
  if (typeof window === 'undefined') return manifests[0]?.dir ?? null;
  const fromHash = window.location.hash.replace(/^#/, '');
  if (fromHash && manifests.some((m) => m.dir === fromHash)) return fromHash;
  return manifests[0]?.dir ?? null;
}

function CodexShell(): React.ReactElement {
  const initialActive = pickInitial();
  const [active, setActive] = useState<string | null>(initialActive);
  // Auto-collapse on initial load if a source is already picked — gives the
  // iframe full width so the upstream site renders in its desktop layout
  // rather than falling back to mobile because of our 220px sidebar.
  const [collapsed, setCollapsed] = useState<boolean>(initialActive !== null);

  useEffect(() => {
    if (!active) return;
    if (window.location.hash.replace(/^#/, '') !== active) {
      window.history.replaceState(null, '', `#${active}`);
    }
  }, [active]);

  useEffect(() => {
    const onHash = () => {
      const fromHash = window.location.hash.replace(/^#/, '');
      if (fromHash && manifests.some((m) => m.dir === fromHash)) {
        setActive(fromHash);
      }
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const onSelect = useCallback((dir: string) => {
    setActive(dir);
    setCollapsed(true);
  }, []);

  const onToggle = useCallback(() => {
    setCollapsed((c) => !c);
  }, []);

  return (
    <div className="codex-shell">
      <LibrarySidebar
        active={active}
        collapsed={collapsed}
        onSelect={onSelect}
        onToggle={onToggle}
      />
      <main className="codex-frame-pane">
        {active ? (
          <iframe
            key={active}
            title={active}
            src={`/sources/${active}/`}
            className="codex-frame"
          />
        ) : (
          <div className="codex-empty">Pick a package to start reading.</div>
        )}
      </main>
    </div>
  );
}

export default function Home(): React.ReactElement {
  return (
    <>
      <Head>
        <title>Codex — Offline documentation viewer</title>
      </Head>
      <BrowserOnly>{() => <CodexShell />}</BrowserOnly>
    </>
  );
}
