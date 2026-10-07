import { projects } from '@/marketing/content/projects';
import type { BidContent } from '@/marketing/content/sections/bid';
import { services } from '@/marketing/content/services';
import { site } from '@/marketing/content/site';
import { BidSection } from './BidSection';

/**
 * "Request a bid". The background is the first project's photo: the reference component falls
 * back to it when no photo is set, and this instance sets none.
 */
export function Bid({ content }: { content: BidContent }) {
  const backdrop = projects[0];
  return (
    <BidSection
      content={content}
      site={{ bidHref: site.bidHref, licence: site.licence, phone: site.phone, proof: site.proof }}
      services={services.map(({ slug, name }) => ({ slug, name }))}
      photo={backdrop?.photo ?? null}
      photoLabel={backdrop?.name ?? ''}
    />
  );
}
