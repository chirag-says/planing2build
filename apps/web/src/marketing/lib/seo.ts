import imgOg from '@/marketing/assets/og.jpg';
import type { Metadata } from 'next';

/** Public origin used for canonical URLs and absolute share links. Set SITE_URL in production. */
export const SITE_URL = process.env.SITE_URL ?? 'https://plan2build.in';

/** The share card: the home page hero, 1200 × 630. */
export const SHARE_IMAGE = imgOg.src;

/**
 * Title, description, canonical path and the matching Open Graph / Twitter fields. `title` is
 * used as is: the public pages carry their own full titles, so the app's "| Plan2Build" template
 * is not added to them.
 */
export function pageMetadata({ title, description, path }: { title: string; description: string; path: string }): Metadata {
  return {
    metadataBase: new URL(SITE_URL),
    title: { absolute: title.includes('Plan2Build') ? title : `${title} | Plan2Build` },
    description,
    alternates: { canonical: path },
    openGraph: { type: 'website', siteName: 'Plan2Build', url: path, title, description, images: [SHARE_IMAGE] },
    twitter: { card: 'summary_large_image', title, description, images: [SHARE_IMAGE] },
  };
}
