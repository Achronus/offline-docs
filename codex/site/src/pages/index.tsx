import React, {useCallback, useEffect, useState} from 'react';
import Head from '@docusaurus/Head';
import BrowserOnly from '@docusaurus/BrowserOnly';
import LibrarySidebar from '@site/src/components/LibrarySidebar';
import {useCatalogue, type Manifest} from '@site/src/data/manifests';

function pickInitial(manifests: Manifest[]): string | null {
  if (manifests.length === 0) return null;
  if (typeof window === 'undefined') return manifests[0]?.dir ?? null;
  const fromHash = window.location.hash.replace(/^#/, '');
  if (fromHash && manifests.some((m) => m.dir === fromHash)) return fromHash;
  return manifests[0]?.dir ?? null;
}

function CodexShell(): React.ReactElement {
  const catalogue = useCatalogue();
  const [active, setActive] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [initialized, setInitialized] = useState(false);

  // Once the catalogue resolves, pick an initial source from the URL hash
  // (if present) or default to the first listed source. Auto-collapse so
  // the iframe gets full viewport width on load.
  useEffect(() => {
    if (initialized) return;
    if (catalogue.status !== 'ready') return;
    const initial = pickInitial(catalogue.manifests);
    setActive(initial);
    setCollapsed(initial !== null);
    setInitialized(true);
  }, [catalogue, initialized]);

  useEffect(() => {
    if (!active) return;
    if (window.location.hash.replace(/^#/, '') !== active) {
      window.history.replaceState(null, '', `#${active}`);
    }
  }, [active]);

  useEffect(() => {
    const onHash = () => {
      if (catalogue.status !== 'ready') return;
      const fromHash = window.location.hash.replace(/^#/, '');
      if (fromHash && catalogue.manifests.some((m) => m.dir === fromHash)) {
        setActive(fromHash);
      }
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, [catalogue]);

  const onSelect = useCallback((dir: string) => {
    setActive(dir);
    setCollapsed(true);
  }, []);

  const onToggle = useCallback(() => {
    setCollapsed((c) => !c);
  }, []);

  if (catalogue.status === 'loading') {
    return <div className="codex-empty">Loading library…</div>;
  }
  if (catalogue.status === 'empty') {
    return (
      <div className="codex-empty">
        No sources staged yet. Run <code>ingest sync</code> to populate.
      </div>
    );
  }

  return (
    <div className="codex-shell">
      <LibrarySidebar
        manifests={catalogue.manifests}
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
