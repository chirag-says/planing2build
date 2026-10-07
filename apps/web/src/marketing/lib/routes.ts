/**
 * Where a link from the reference site lands in this app.
 *
 * The public pages are `/`, `/services`, `/for-homeowners` and `/for-professionals`; the homeowner
 * journey starts at `/start`. Links to the reference's other pages go to the section that covers
 * the same thing, so nothing leads to a 404. When a page is added, delete its entry here.
 */
const SECTION_FOR_PATH: Array<[RegExp, string]> = [
  [/^\/request-a-bid(\?.*)?$/, '/start$1'],
  [/^\/projects(\/.*)?$/, '/#built'],
  // Each service row carries its slug as an id.
  [/^\/services\/([\w-]+)$/, '/services#$1'],
  [/^\/safety$/, '/#safety'],
  [/^\/(team|about)(\/.*)?$/, '/#crew'],
  [/^\/for-contractors$/, '/for-professionals'],
  [/^\/(careers|journal|contact|privacy|terms|cookies)(\/.*)?$/, '#contact'],
];

export function resolveHref(href: string): string {
  if (!href.startsWith('/')) return href;
  for (const [pattern, target] of SECTION_FOR_PATH) if (pattern.test(href)) return href.replace(pattern, target);
  return href;
}

/** True for links that stay on this site. */
export const isInternal = (href: string) => href.startsWith('/') || href.startsWith('#');
