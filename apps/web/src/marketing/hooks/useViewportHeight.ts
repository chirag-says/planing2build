'use client';

import { useSyncExternalStore } from 'react';

/** Height assumed during server rendering, as the reference's server render did. */
const SERVER_GUESS = 900;

function subscribe(onChange: () => void) {
  window.addEventListener('resize', onChange);
  return () => window.removeEventListener('resize', onChange);
}

/** The window's inner height, kept current on resize. */
export function useViewportHeight(): number {
  return useSyncExternalStore(
    subscribe,
    () => window.innerHeight,
    () => SERVER_GUESS,
  );
}
