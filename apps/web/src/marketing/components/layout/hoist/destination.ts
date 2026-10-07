/**
 * Which clicks the hoist takes over, and what the plate says about where they lead.
 */

/** Link text that says what the link does rather than where it goes; never shown as a name. */
const GENERIC_LINK_TEXT =
  /^(read|learn more|open|more|see|view|go|get|book|start|apply|all|back|browse|meet|build|request|→|#|\$|\d)/i;
/** Longer link text is a sentence, not a page name. */
const MAX_NAME_LENGTH = 28;

export const trimPath = (path: string) => path.replace(/\/+$/, '') || '/';

function decode(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

/**
 * The internal URL a click should hoist to, or null to leave the click alone: modified clicks,
 * other windows, downloads, other origins, non-page schemes, opt-outs (`data-no-trans`) and any
 * link that stays on the current page (hash links included).
 */
export function hoistTarget(event: MouseEvent): { url: URL; anchor: HTMLAnchorElement } | null {
  if (event.defaultPrevented || event.button !== 0) return null;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return null;
  const anchor = (event.target as Element | null)?.closest?.('a[href]');
  if (!(anchor instanceof HTMLAnchorElement)) return null;
  if ((anchor.target && anchor.target !== '_self') || anchor.hasAttribute('download') || anchor.closest('[data-no-trans]')) {
    return null;
  }
  const raw = anchor.getAttribute('href') ?? '';
  if (/^(mailto|tel|sms|javascript):/i.test(raw) || raw.startsWith('#')) return null;

  let url: URL;
  try {
    url = new URL(anchor.href, location.href);
  } catch {
    return null;
  }
  if (url.origin !== location.origin || !/^https?:$/.test(url.protocol)) return null;
  if (trimPath(url.pathname) === trimPath(location.pathname)) return null;
  return { url, anchor };
}

/**
 * The name on the plate: the configured name for the path, the home label for `/`, else the
 * link's own text when it reads like a page name, else the last path segment in title case.
 */
export function destinationName(url: URL, anchor: HTMLAnchorElement, names: Map<string, string>, homeLabel: string): string {
  const named = names.get(trimPath(url.pathname));
  if (named) return named;
  const segments = url.pathname.split('/').filter(Boolean);
  if (!segments.length) return homeLabel;

  const firstLine = anchor.innerText.split('\n').map((line) => line.trim()).find(Boolean) ?? '';
  const text = (anchor.getAttribute('aria-label') || firstLine).replace(/\s+/g, ' ').trim();
  if (text && text.length <= MAX_NAME_LENGTH && !GENERIC_LINK_TEXT.test(text)) return text;
  return decode(segments.at(-1) ?? '')
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/** The path chip under the name: `/services` → "/services", `/a/b` → "/a / b". */
export function pathLabel(pathname: string): string {
  return '/' + pathname.split('/').filter(Boolean).map(decode).join(' / ');
}
