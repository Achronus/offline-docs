// Library catalogue is fetched at runtime from /sources/_catalogue.json,
// which the ingest CLI regenerates after every successful stage.

import {useEffect, useState} from 'react';

export type Manifest = {
  dir: string;
  name: string;
  tag: string;
  color: string;
  version: string;
  page_count: number;
  source_url?: string;
  fetched_at?: string;
  favicon?: string | null;
};

export type CatalogueState =
  | {status: 'loading'}
  | {status: 'ready'; manifests: Manifest[]}
  | {status: 'empty'};

export function useCatalogue(): CatalogueState {
  const [state, setState] = useState<CatalogueState>({status: 'loading'});

  useEffect(() => {
    let cancelled = false;
    fetch('/sources/_catalogue.json', {cache: 'no-cache'})
      .then((r) => (r.ok ? r.json() : []))
      .then((data: Manifest[]) => {
        if (cancelled) return;
        if (!Array.isArray(data) || data.length === 0) {
          setState({status: 'empty'});
        } else {
          setState({status: 'ready', manifests: data});
        }
      })
      .catch(() => {
        if (!cancelled) setState({status: 'empty'});
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
