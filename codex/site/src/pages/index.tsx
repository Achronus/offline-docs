import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import Head from '@docusaurus/Head';
import BrowserOnly from '@docusaurus/BrowserOnly';
import Landing from '@site/src/components/Landing';
import LibrarySidebar from '@site/src/components/LibrarySidebar';
import {useCatalogue, type Manifest} from '@site/src/data/manifests';

function CodexFrame({source}: {source: string}): React.ReactElement {
  const ref = useRef<HTMLIFrameElement>(null);
  const [loading, setLoading] = useState(true);

  const onLoad = useCallback(() => {
    setLoading(false);
    const frame = ref.current;
    if (!frame) return;
    const doc = frame.contentDocument || frame.contentWindow?.document;
    if (!doc) return;
    // Show spinner the instant the user clicks a navigation link inside the
    // iframe, so the loading state is visible before the browser starts
    // unloading the current page.
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented) return;
      if (e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.('a');
      if (!a || !(a instanceof HTMLAnchorElement)) return;
      if (a.target === '_blank') return;
      const href = a.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
      setLoading(true);
    };
    doc.addEventListener('click', onClick, true);
  }, []);

  return (
    <div className="codex-frame-wrapper">
      <iframe
        ref={ref}
        title={source}
        src={`/sources/${source}/`}
        className="codex-frame"
        onLoad={onLoad}
      />
      {loading && (
        <div className="codex-frame-loader" role="progressbar" aria-label="Loading" />
      )}
    </div>
  );
}

function CodexShell(): React.ReactElement {
  const catalogue = useCatalogue();
  const [active, setActive] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(false);
  const [initialized, setInitialized] = useState(false);

  // Sort by display name. The catalogue's natural order is codex.yaml's,
  // but the library UX wants packages alphabetised.
  const manifests: Manifest[] = useMemo(() => {
    if (catalogue.status !== 'ready') return [];
    return [...catalogue.manifests].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, {sensitivity: 'base'}),
    );
  }, [catalogue]);

  // Resolve initial source from URL hash; if none, stay on the landing page.
  useEffect(() => {
    if (initialized || catalogue.status !== 'ready') return;
    const hash = window.location.hash.replace(/^#/, '');
    if (hash && manifests.some((m) => m.dir === hash)) {
      setActive(hash);
      setCollapsed(true);
    }
    setInitialized(true);
  }, [catalogue, manifests, initialized]);

  // Reflect selection in URL hash so links + back/forward work.
  useEffect(() => {
    if (!initialized) return;
    const desired = active ?? '';
    const current = window.location.hash.replace(/^#/, '');
    if (current !== desired) {
      window.history.replaceState(null, '', desired ? `#${desired}` : window.location.pathname);
    }
  }, [active, initialized]);

  useEffect(() => {
    const onHash = () => {
      if (catalogue.status !== 'ready') return;
      const hash = window.location.hash.replace(/^#/, '');
      if (!hash) {
        setActive(null);
        setCollapsed(false);
      } else if (manifests.some((m) => m.dir === hash)) {
        setActive(hash);
        setCollapsed(true);
      }
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, [catalogue, manifests]);

  const onSelect = useCallback((dir: string) => {
    setActive(dir);
    setCollapsed(true);
  }, []);

  const onToggle = useCallback(() => setCollapsed((c) => !c), []);

  const onHome = useCallback(() => {
    setActive(null);
    setCollapsed(false);
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
        manifests={manifests}
        active={active}
        collapsed={collapsed}
        onSelect={onSelect}
        onToggle={onToggle}
        onHome={onHome}
      />
      <main className="codex-frame-pane">
        {active ? (
          <CodexFrame key={active} source={active} />
        ) : (
          <Landing manifests={manifests} onSelect={onSelect} />
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
