/**
 * While the first-visit loader or the page-transition cover is on screen, <html> carries a
 * `gd-hold-*` class. Section entrances wait for it to clear so they play where the visitor can
 * see them. The wait is capped so content can never stay hidden.
 */
const HOLD_CLASS = /(^|\s)gd-hold/;
const MAX_WAIT_MS = 9000;

export const HOLD = {
  loader: 'gd-hold-ld',
  transition: 'gd-hold-pt',
} as const;

export function isHeld(): boolean {
  return HOLD_CLASS.test(document.documentElement.className);
}

/** Calls `release` once nothing holds the page. Returns a cancel function. */
export function whenReleased(release: () => void): () => void {
  if (!isHeld()) {
    release();
    return () => {};
  }
  const root = document.documentElement;
  const done = () => {
    observer.disconnect();
    window.clearTimeout(timer);
    release();
  };
  const observer = new MutationObserver(() => {
    if (!isHeld()) done();
  });
  observer.observe(root, { attributes: true, attributeFilter: ['class'] });
  const timer = window.setTimeout(done, MAX_WAIT_MS);
  return () => {
    observer.disconnect();
    window.clearTimeout(timer);
  };
}
