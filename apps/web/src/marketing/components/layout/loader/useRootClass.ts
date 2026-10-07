'use client';

import { useSyncExternalStore } from 'react';

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
  return () => observer.disconnect();
}

/**
 * Whether <html> carries `name`, kept live. `serverValue` is what the server render assumed;
 * React re-renders right after hydration if the document says otherwise.
 */
export function useRootClass(name: string, serverValue: boolean): boolean {
  return useSyncExternalStore(
    subscribe,
    () => document.documentElement.classList.contains(name),
    () => serverValue,
  );
}
