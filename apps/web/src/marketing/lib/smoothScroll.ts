import type Lenis from 'lenis';

/**
 * Access to the page's smooth scroller. SmoothScroll registers the Lenis instance here when it is
 * active (fine pointer, motion allowed); everything else scrolls through `scrollPageTo`, which
 * falls back to native scrolling when there is no instance.
 */
let scroller: Lenis | null = null;

export function registerSmoothScroller(instance: Lenis | null) {
  scroller = instance;
}

export function getSmoothScroller(): Lenis | null {
  return scroller;
}

/** `duration` (seconds) applies to the smooth scroller only; native scrolling picks its own. */
type ScrollOptions = { offset?: number; immediate?: boolean; duration?: number };

export function scrollPageTo(target: number | HTMLElement, { offset = 0, immediate = false, duration }: ScrollOptions = {}) {
  if (scroller) {
    scroller.scrollTo(target, { offset, immediate, force: true, ...(duration === undefined ? {} : { duration }) });
    return;
  }
  const top = typeof target === 'number' ? target : target.getBoundingClientRect().top + window.scrollY;
  window.scrollTo({ top: top + offset, behavior: immediate ? 'instant' : 'smooth' });
}
