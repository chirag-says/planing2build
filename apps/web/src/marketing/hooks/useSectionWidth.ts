'use client';

import { useLayoutEffect, useState, type RefObject } from 'react';

/** Width assumed before measuring, as the reference's server render did. */
const DESKTOP_GUESS = 1440;

/**
 * The element's rendered width, for the few choices CSS cannot make: markup that differs by
 * breakpoint, or arithmetic that does. Styling itself uses `@container site` queries.
 */
export function useSectionWidth(ref: RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(DESKTOP_GUESS);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const measured = Math.round(entry?.borderBoxSize?.[0]?.inlineSize || el.offsetWidth);
      if (measured > 0) setWidth(measured);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}
