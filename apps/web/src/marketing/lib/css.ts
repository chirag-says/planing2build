import type { CSSProperties } from 'react';

/** Inline style that may also set CSS custom properties (`--name`). */
export type StyleWithVars = CSSProperties & { [variable: `--${string}`]: string | number | undefined };

/**
 * Style for an element that fades and rises in when its section reveals (class `gd-rv`).
 * `delay` in ms, `distance` in px.
 */
export const revealDelay = (delay = 0, distance?: number): StyleWithVars => ({
  '--rv-d': `${delay}ms`,
  ...(distance === undefined ? {} : { '--rv-y': `${distance}px` }),
});
