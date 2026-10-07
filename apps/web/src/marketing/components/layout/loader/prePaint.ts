import { HOLD } from '@/marketing/lib/hold';

/** On <html> while the loader is on screen. Shows it and locks scrolling (loader.css). */
export const LOADER_ON = 'loader-go';
/** On <html> once the lift-off has started: scrolling is allowed again. */
export const LOADER_OPEN = 'loader-open';
/** Set on <html> while the loader runs: the intro's pace (loader.css). */
export const LOADER_PACE = '--loader-k';
/** Set when a visit has seen the loader, so later page loads in the same tab skip it. */
export const SEEN_KEY = 'gd-loaded';
/** If the app has not started the loader by then (it failed to hydrate), uncover the page. */
const ABANDON_MS = 6000;

/**
 * Inline script that runs while the HTML is parsed, before the page paints. It decides whether
 * this visit gets the loader and, if so, puts the classes on <html> that show it and hold the
 * section reveals. Without it the page would flash before React could cover it.
 */
export function prePaintScript(once: boolean): string {
  const skipIfSeen = once ? `if (sessionStorage.getItem('${SEEN_KEY}')) return;` : '';
  return `(function () {
  try {
    var root = document.documentElement;
    ${skipIfSeen}
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    root.classList.add('${LOADER_ON}', '${HOLD.loader}');
    setTimeout(function () {
      if (!root.style.getPropertyValue('${LOADER_PACE}')) root.classList.remove('${LOADER_ON}', '${HOLD.loader}');
    }, ${ABANDON_MS});
  } catch (error) {}
})();`;
}
