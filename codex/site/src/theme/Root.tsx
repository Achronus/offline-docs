import React, {type ReactNode} from 'react';
import LibrarySidebar from '@site/src/components/LibrarySidebar';

export default function Root({children}: {children: ReactNode}): React.ReactElement {
  return (
    <div style={{display: 'flex', minHeight: '100vh'}}>
      <LibrarySidebar />
      <div style={{flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column'}}>
        {children}
      </div>
    </div>
  );
}
