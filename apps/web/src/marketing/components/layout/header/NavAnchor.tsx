import Link from 'next/link';
import type { ComponentPropsWithoutRef } from 'react';
import { resolveHref } from '@/marketing/lib/routes';

type NavAnchorProps = Omit<ComponentPropsWithoutRef<'a'>, 'href'> & { href: string };

/** A header link: the reference path is resolved to its place in this app, and site routes
 * navigate client-side. */
export function NavAnchor({ href, ...rest }: NavAnchorProps) {
  const target = resolveHref(href);
  return target.startsWith('/') ? <Link href={target} {...rest} /> : <a href={target} {...rest} />;
}
