import type { CSSProperties } from 'react';

/**
 * The three type faces, applied as inline styles exactly where the reference applied them.
 * Inline matters: these declarations outrank every stylesheet rule on the same element, and
 * several section stylesheets rely on that (for example `.gd-hd` declares a lighter weight that
 * the display face must override).
 */
export const TYPE = {
  display: { fontFamily: 'var(--font-display)', fontWeight: 800, fontStyle: 'normal' },
  body: { fontFamily: 'var(--font-body)', fontWeight: 400 },
  mono: { fontFamily: 'var(--font-mono)', fontWeight: 400 },
} satisfies Record<string, CSSProperties>;
